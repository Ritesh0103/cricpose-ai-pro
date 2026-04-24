#====================================================================================================
# START - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================
# Preserved - testing data follows below.
#====================================================================================================
# END - Testing Protocol - DO NOT EDIT OR REMOVE THIS SECTION
#====================================================================================================

user_problem_statement: |
  Continue development of the existing CricPose AI Pro project (React + FastAPI + MongoDB + MediaPipe).
  Do NOT rebuild from scratch. Preserve premium dark sports-tech UI, existing routes, backend
  architecture, upload/analysis pipeline. After porting the uploaded codebase into /app, add these
  smart continuations:
    1) Dashboard upgrade — Latest Session card, Progress chart, Weekly trend, Compare CTA
    2) CSV export endpoints (metrics, frame-level motion, events) + frontend download buttons
    3) Wire existing advanced charts (BoxPlotCard, SymmetryChart, RiskHeatmapStrip,
       JointTrajectoryChart, BarComparisonCard) into the Analysis dashboard
    4) Compare page — add MultiProRadar overlay + multi-select pro chips + preselect from ?report=
    5) Handle 0/100 landing-balance display — confirmed already returns "—" via existing fmt()
    6) Full signup→upload→compare→dashboard end-to-end test
    7) Deployment hardening check
  User credentials: test@cricpose.ai / test1234

backend:
  - task: "Backend port from uploaded zip into /app (auth, analysis, compare, reports, users, health)"
    implemented: true
    working: true
    file: "backend/server.py, backend/app/*"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: true
        agent: "main"
        comment: "Ported from extracted /tmp/cricpose_extracted/cricpose-ai-pro-main. Installed mediapipe 0.10.14, opencv-python-headless 4.10.0.84, opencv-contrib-python 4.11.0.86, reportlab 4.2.2, PyJWT 2.12.1. Backend /api/health 200, auth/login/signup/me/dashboard/compare/profiles all respond correctly."

  - task: "CSV export endpoints /api/analysis/{id}/csv/{metrics|motion|events}"
    implemented: true
    working: "NA"
    file: "backend/app/services/csv_service.py, backend/app/routes/analysis.py"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "New csv_service.py with build_metrics_csv (flat summary with all scores/joint metrics/classification/injury), build_motion_csv (wide-format per-frame joining arm angle, shoulder alignment, knee bends, trunk flexion, pelvis-shoulder sep, wrist trajectory x/y, L/R knee, risk band), build_events_csv (BFC/FFC/Release/Follow-through). Route GET /api/analysis/{report_id}/csv/{kind} added. 400 for unknown kind, 404 for missing report (via get_report)."

frontend:
  - task: "Dashboard upgrade — Latest session card, ProgressChart, Weekly trend, Compare CTA"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/DashboardPage.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Rewrote DashboardPage: 4 stat cards (sessions/avg/best/injury-band), ProgressChart using score_trend array (overall + efficiency + injury), Latest-session panel showing action_label, release speed, overall score, injury probability + open/compare buttons, Weekly improvement meter (delta over trend window), Compare-with-pros CTA card with 7 pro chips. All data-testid: dashboard-stats, stat-*, latest-session-card, latest-action/speed/score/injury, chart-progress, weekly-summary-card, compare-cta-card, compare-cta-btn, latest-open-btn, latest-compare-btn."

  - task: "Analysis dashboard advanced charts + CSV export buttons"
    implemented: true
    working: "NA"
    file: "frontend/src/components/AnalysisDashboard.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added 3 CSV download buttons alongside PDF (download-csv-metrics-btn, download-csv-motion-btn, download-csv-events-btn). Added Compare-link card linking to /compare?report={id}. Wired in: RiskHeatmapStrip (motion.risk_heatmap), 4x BarComparisonCard (front knee FFC, front knee BR, peak vGRF, ball release speed vs elite benchmarks), 4x BoxPlotCard (shoulder alignment, pelvis-shoulder separation, trunk lateral flexion, front knee bend from distribution_stats), SymmetryChart (motion.symmetry), JointTrajectoryChart (motion.wrist_trajectory). Existing PDF button + all previous panels preserved."

  - task: "Compare page — MultiProRadar overlay + multi-select + ?report= preselect"
    implemented: true
    working: "NA"
    file: "frontend/src/pages/ComparePage.jsx"
    stuck_count: 0
    priority: "high"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added MultiProRadar panel with toggleable pro chips (defaults to first 3 profiles), fetches athleteReport alongside compare data to feed athleteMetrics. ?report= query param preselects analysisId. data-testid: multi-pro-overlay-panel, pro-overlay-chips, overlay-chip-<name>."

  - task: "lib/api.js — downloadCSV helper"
    implemented: true
    working: "NA"
    file: "frontend/src/lib/api.js"
    stuck_count: 0
    priority: "medium"
    needs_retesting: true
    status_history:
      - working: "NA"
        agent: "main"
        comment: "Added api.downloadCSV(reportId, kind) wrapping api.downloadFile with bearer auth."

metadata:
  created_by: "main_agent"
  version: "2.0"
  test_sequence: 5
  run_ui: true

test_plan:
  current_focus:
    - "Backend port from uploaded zip into /app"
    - "CSV export endpoints /api/analysis/{id}/csv/{metrics|motion|events}"
    - "Dashboard upgrade — Latest session card, ProgressChart, Weekly trend, Compare CTA"
    - "Analysis dashboard advanced charts + CSV export buttons"
    - "Compare page — MultiProRadar overlay + multi-select + ?report= preselect"
  stuck_tasks: []
  test_all: true
  test_priority: "high_first"

agent_communication:
  - agent: "main"
    message: |
      Ported CricPose AI Pro from uploaded zip into /app. All deps installed (mediapipe, opencv,
      reportlab, PyJWT). Services supervised and running. Added 3 CSV export endpoints + frontend
      download buttons. Upgraded DashboardPage with ProgressChart/Latest session/Weekly trend/
      Compare CTA. Wired BoxPlot (4x), SymmetryChart, RiskHeatmapStrip, JointTrajectoryChart,
      BarComparisonCard (4x) into AnalysisDashboard. Added MultiProRadar + multi-select chips +
      ?report= preselect to ComparePage. Test credentials: test@cricpose.ai / test1234. Please run
      end-to-end: signup → login → upload bowling clip → analysis dashboard (verify all 5 video tabs,
      15 metric tiles, 4 BoxPlots, SymmetryChart, RiskHeatmap, JointTrajectory, 4 BarComparisons,
      CSV downloads) → compare page with MultiProRadar toggles → dashboard latest-session + progress
      chart. No test video is pre-shipped; please use any bowling-action video you have, or upload a
      short generic sports video — the pipeline is designed to run on single-camera footage.
