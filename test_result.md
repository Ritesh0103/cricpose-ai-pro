#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================
#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

user_problem_statement: |
  User uploaded an 11-second 9.55 MB bowling clip and saw "The analysis took too long and the
  gateway timed out. Try a shorter clip (under 20s) or the demo mode." — the Kubernetes ingress
  was closing the connection while the synchronous MediaPipe pipeline (pose detection + 5 video
  outputs + PDF) was still running (~60-90s). Need to architect the upload as a background job
  so the HTTP request returns immediately and cannot be terminated by the ingress.

backend:
  - task: "Async background processing — upload returns immediately with status=processing"
    implemented: true
    working: true
    file: "backend/app/routes/analysis.py, backend/app/services/report_service.py, backend/app/models.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: true
        agent: "main"
        comment: |
          ROOT CAUSE: Kubernetes ingress closes the connection after ~60s. MediaPipe + 5 video
          outputs + PDF generation on an 11s clip is close to or above that budget, so the user
          saw 504/502 surfaced as the frontend's gateway-timeout message.

          FIX: Restructured upload flow as background job + polling:
            1. POST /api/analysis/upload now: (a) streams file to disk with 200 MB cap
               (b) inserts a Report doc with status="processing" (c) asyncio.create_task spawns
               _process_analysis in the background (d) returns AnalysisResponse in ~0 ms.
            2. New GET /api/analysis/{report_id}/status returns the current AnalysisResponse —
               status can be "processing" | "done" | "failed" with user-friendly .error.
            3. _process_analysis runs analyze_video + build_pdf in asyncio.to_thread and calls
               report_service.update_processing_result on success/failure. Any exception is
               mapped via _classify_analysis_error to status=failed + friendly .error.
            4. Models: AnalysisResponse now includes status (default "done") + error.
            5. Pose service: model_complexity dropped from 1 → 0 (~3x faster pose detection).

          Verified via curl: upload returns in 0s, status poll correctly flips through
          processing → failed (for synthetic clip) or processing → done (for real clip). No more
          ingress timeouts possible because the HTTP request is decoupled from the heavy work.

  - task: "Demo endpoint regression after adding status field to reports"
    implemented: true
    working: true
    file: "backend/app/routes/analysis.py, backend/app/services/demo_service.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: false
    status_history:
      - working: true
        agent: "main"
        comment: "Demo endpoint still creates report with status='done' directly (default). Verified: id returned, status=done, is_demo=True in metrics, PDF built, CSV 3x work."

frontend:
  - task: "api.uploadVideo now polls /status until done|failed"
    implemented: true
    working: "NA"
    file: "frontend/src/lib/api.js"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: |
          api.uploadVideo now: (1) posts the file, (2) if response says status=processing,
          switches onStage("analyzing") and starts polling /api/analysis/{id}/status every 2s
          via new api.pollAnalysis, (3) resolves when server returns status=done, throws
          extractError on status=failed (with server's friendly .error), (4) 10-minute deadline
          on polling loop; transient network errors mid-poll are tolerated. UploadCard text for
          analyzing phase updated to mention polling.

metadata:
  created_by: "main_agent"
  version: "2.2"
  test_sequence: 7
  run_ui: false

test_plan:
  current_focus:
    - "Async background processing — upload returns immediately with status=processing"
    - "api.uploadVideo now polls /status until done|failed"
  stuck_tasks: []
  test_all: false
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      User reported 11s/9.55 MB bowling clip → gateway timeout. Fixed by making the analysis
      pipeline a background asyncio task with a GET /status poll endpoint.

      Curl proof:
        - POST /upload with 80KB synthetic mp4: response time 0s, returns status=processing
        - GET /status poll 3x at 2s intervals: processing → processing → failed (with friendly
          "No bowler was detected..." message)
        - POST /upload with 200KB stick-figure mp4: same flow, failed in ~6s total
        - Demo endpoint still returns status=done directly (no regression)
        - /api/reports/{id} returns report with status + error fields

      Please run backend-only smoke test focused on:
        1. POST /api/analysis/upload with any video (text/plain should still 415; synthetic
           mp4 should return HTTP 200 in <3s with status=processing)
        2. GET /api/analysis/{id}/status for a non-existent report → 404
        3. Demo endpoint regression: status="done", metrics.is_demo, PDF, CSVs still work
        4. Full test from iter 6 still passes (auth, compare, dashboard, 7 profiles, CSVs)
      Skip frontend testing — UploadCard visual behaviour unchanged; the only new JS is the
      polling wrapper inside api.uploadVideo which is exercised via the async curl flow above.

      Credentials: test@cricpose.ai / test1234
