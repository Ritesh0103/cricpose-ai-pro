# CricPose AI Pro — Product Requirements

## Original problem
User uploaded an existing CricPose AI Pro project (React + FastAPI + MongoDB + MediaPipe pose
analysis for cricket bowling biomechanics). Brief: continue development smartly without rebuilding.
Preserve premium dark sports-tech UI, routes, branding, existing backend architecture. Add
dashboard upgrades, CSV export, advanced graphs wiring, and Compare MultiProRadar overlay.

## Architecture
- **Frontend**: React 19 (CRA + craco), React Router 7, shadcn/ui, recharts, axios, localStorage JWT.
- **Backend**: FastAPI, motor (MongoDB), MediaPipe Pose 0.10.14, OpenCV (headless + contrib),
  reportlab for PDF, bcrypt + PyJWT for auth, csv (stdlib) for exports.
- **Storage**: `/app/backend/storage/{uploads,processed,reports,temp}`.
- **Auth**: email/password with bcrypt (72-byte safe truncation), JWT HS256, guest login path,
  14-day access tokens.

## User personas
- **Amateur/club bowler** — uploads practice clips, tracks progression across sessions, gets
  coaching tips from AI deltas vs elite benchmarks.
- **Coach** — reviews athlete sessions in the History table, exports PDF + 3 CSVs per session for
  performance docs, compares athletes against Bumrah/Starc/Steyn/Cummins benchmark profiles.
- **Sport-science researcher** — taps the frame-by-frame motion CSV for downstream analysis,
  correlates metrics with injury-probability band.

## Core requirements (static)
1. Signup/login/guest auth with saved session history per user.
2. Upload MP4/MOV/WebM bowling clip → pose detection → 5 video outputs → metrics → MongoDB.
3. Research-grade biomechanics: release angle/speed/height, wrist velocity, hip rotation speed,
   pelvis-shoulder separation, trunk lateral flexion, front-knee flexion FFC/BR, vGRF, stride
   length, run-up speed, landing balance, L/R symmetry.
4. Portus/Ferdinands action classification + composite injury probability (7-factor).
5. 5 video outputs streamed with HTTP Range (206): original, skeleton overlay, joint trails,
   side-by-side, release slow-mo.
6. Compare vs 7 elite profiles (Bumrah, Starc, Shami, Brett Lee, Anderson, Steyn, Cummins) with
   12-metric weighted similarity + radar + strengths/weaknesses/tips.
7. Coach-friendly PDF + CSV exports (metrics, motion, events).
8. Dashboard with score trend, latest session highlight, weekly improvement meter.

## What's been implemented (dates: Feb 2026)
### Iteration 1-4 (inherited from uploaded codebase)
- Full auth (JWT + bcrypt) + 8 frontend pages + 5 video outputs with Range streaming
- 15-signal biomechanics + action classification + injury probability + 7-entry risk list
- 7 elite benchmark profiles + weighted compare + radar + coaching tips
- PDF report generation (reportlab), skeleton+trails+slowmo+side-by-side+original

### Iteration 5 (current — smart continuation, Feb 2026)
- Ported uploaded project into `/app`; installed mediapipe/opencv/reportlab/PyJWT
- **CSV export** (`csv_service.py`): build_metrics_csv (flat summary), build_motion_csv
  (wide-format frame-by-frame), build_events_csv (BFC/FFC/Release/Follow-through). Endpoint
  `GET /api/analysis/{id}/csv/{metrics|motion|events}` with 400 for unknown kinds.
- **DashboardPage upgrade**: 4 stat cards with icon badges + injury band, ProgressChart (area with
  overall + efficiency + injury-probability lines) with empty-state placeholder, Latest Session
  card (action label + release speed + overall + injury probability + open/compare buttons),
  Weekly improvement meter (delta + progress bar), Compare-with-pros CTA with 7 bowler chips.
- **AnalysisDashboard advanced graphs**: wired in RiskHeatmapStrip, 4x BarComparisonCard (front
  knee FFC/BR, peak vGRF, ball release speed), 4x BoxPlotCard (shoulder alignment, pelvis-shoulder
  separation, trunk lateral flexion, front knee bend distributions), SymmetryChart,
  JointTrajectoryChart. 3 CSV buttons + existing PDF + Compare-link card.
- **ComparePage**: MultiProRadar overlay panel visible upfront (not gated behind submitted
  compare), toggleable pro chips, `?report=` query-param preselect, fetches athleteReport
  alongside compare data for overlay.
- Test credentials file updated.

## Test status (iteration 5, Apr 2026)
- Backend: **14/14 runnable tests pass** (auth, dashboard shape, 7 compare profiles, CSV
  unknown→400, reports 404, upload validations). 12 upload-dependent tests gracefully skip when no
  real bowling clip is present.
- Frontend: **~90% pass**, all 8 new dashboard data-testids render correctly. Upload-dependent
  flows (AnalysisDashboard render, CSV downloads, ?report= preselect overlay with athlete data)
  require a real bowling clip to exercise end-to-end.

## Backlog (P0/P1/P2)
- **P0** (next): Kaggle dataset ingestion pipeline — scan folders, detect bowler names, extract
  frames, run pose detection, cluster styles, build benchmark profiles from real data (currently
  profiles are literature-tuned). Bundle a sample bowling clip in `/app/backend/storage/samples/`
  so end-to-end testing passes fully.
- **P1**: Multi-camera calibration, radar ground-truth calibration, 3D lifted pose, team
  workspaces, share-link for public reports, admin console.
- **P2**: Session notes, video clip annotations, Slack/Discord share-outs, cloud storage backend
  (S3), mobile-native app shell, LLM coaching chat on top of metrics.

## Next action items
1. Source or commit a sample bowling MP4 clip to unlock full end-to-end testing of upload flow.
2. Build the Kaggle ingestion pipeline and rebuild elite profiles from real pose averages.
3. Add rate limiting + request-size limits to the /api/analysis/upload endpoint for production.
4. Add OpenGraph + Twitter meta tags for share-link SEO.
5. Consider deploying backend to Railway/Render and frontend to Vercel/Netlify with a production
   Mongo Atlas cluster.
