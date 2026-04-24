# CricPose AI Pro — Product Requirements

## Original problem
User uploaded an existing CricPose AI Pro project (Next.js + FastAPI + SQLite + MediaPipe). The
brief required inspection, repair, and a research-grade biomechanics upgrade while preserving
branding, routes, theme, and reusable components. User picked path **1c — hybrid inspect + rebuild
MVP** in our React (CRA) + FastAPI + MongoDB stack.

## Architecture (iteration 1)
- **Frontend:** React 19 (CRA), React Router 7, shadcn/ui, recharts, axios, localStorage JWT.
- **Backend:** FastAPI, motor (MongoDB), MediaPipe Pose, OpenCV, reportlab for PDF, bcrypt + PyJWT.
- **Storage:** `/app/backend/storage/{uploads,processed,reports,temp}` (video, overlay, PDF, thumb).
- **Auth:** email/password with bcrypt 72-byte safe truncation, JWT HS256, guest login path.

## Research-grade metrics implemented (Feb 2026 — iteration 3)
**Core joint metrics (15 signals)**
- Shoulder alignment, pelvis-shoulder (hip-shoulder) separation at release
- Trunk lateral flexion at release
- Front knee flexion at FFC and at ball release + FFC→BR change (brace quality)
- vGRF (body weights + newtons) via COM deceleration
- Ball release speed (kph, wrist tangential velocity × moment arm)
- Ball release angle (arm vs vertical)
- **Ball release height** (metres from bowling wrist to mean foot at FFC)
- Stride length (metres) at FFC
- Run-up speed (kph)
- **Hip rotation speed** (degrees/sec between FFC and release)
- **Wrist velocity** (m/s at release, linear)
- Follow-through balance + run-up consistency
- **Landing balance score** (COM-x stability in the 0.15s after FFC)
- **L/R kinematic symmetry score**

**Action classification** (Portus/Ferdinands style):
- Side-on / Front-on / Semi-open / Mixed — inferred from shoulder alignment at BFC vs FFC
- Returned as `classification {action_type, action_label, confidence, shoulder_at_bfc/ffc/delta, description}`

**Injury analysis** (composite probability 0-100 + band Low/Moderate/High):
- Contributors: trunk lateral flexion >30° (+25), mixed action (+30), vGRF >7 BW (+18), front knee hyperextension (+12), poor landing mechanics (+10), L/R asymmetry (+8)
- `injury_risk` array now 7 entries (Lumbar, Knee Load, Shoulder Drift, Mixed-action, Hyperextension, Landing, Asymmetry)

**Benchmark roster**: Bumrah, Starc, Shami, Brett Lee, Anderson, Steyn, **Cummins** — returned as "You bowl X% similar to <bowler>".

## Event detection
- Back-foot contact (BFC): back ankle lowest point prior to FFC
- FFC: front-ankle vertical velocity zero-crossing (or lowest point in window)
- Ball release (BR): bowling-wrist peak vertical position
- Follow-through: ~0.35s after release

## Video processing outputs (Feb 2026 — iteration 2)
1. **Original**: clean uploaded clip at `/api/analysis/{id}/source`
2. **Skeleton overlay**: 33 MediaPipe landmarks + connections at `/api/analysis/{id}/video`
3. **Joint-trail tracking**: fading cyan/green/warm trails for bowling-side shoulder/wrist/ankle at
   `/api/analysis/{id}/tracking`
4. **Side-by-side comparison**: original | skeleton horizontally concatenated at
   `/api/analysis/{id}/sidebyside`
5. **Release slow-motion**: ±1.2s window around auto-detected ball release at 1/3 playback speed at
   `/api/analysis/{id}/slowmo`
All endpoints support HTTP Range requests (206 Partial Content), are bearer-protected, and the
frontend AnalysisDashboard exposes them as a 5-tab video viewer.

## Key features shipped
- Landing, login, signup, dashboard, analysis, compare, history, settings pages
- Upload → pose → metrics → MongoDB → PDF pipeline
- Skeleton-overlay video output + thumbnail capture
- Recharts line charts (bowling arm, knee flexion, trunk flexion, pelvis-shoulder separation)
- Compare section with 6 elite profiles (Bumrah, Starc, Shami, Brett Lee, Anderson, Steyn) and a
  weighted similarity score with radar + bar chart breakdown
- Session history table and dashboard KPI cards
- Protected video streaming with HTTP range support

## Core routes (`/api`)
- `auth`: signup, login, guest, me, logout
- `users`: /me, /dashboard
- `analysis`: upload, streamed source/video/thumbnail per report
- `reports`: list, detail, PDF
- `compare`: profiles list, POST compare

## Backlog (P0/P1/P2)
- **P0**: wire Kaggle Steyn/Bumrah reference clips into compare page silhouette + side-by-side video
  (currently shows stylised reference). Add bulk upload. 
- **P1**: multi-camera calibration, radar ground-truth calibration for release speed, 3D lifted pose,
  export to CSV, team workspaces.
- **P2**: athlete progress charts, session notes, share link, cloud storage, admin console.

## Next action items
1. Seed Kaggle pro-bowler clips and wire into compare visualiser.
2. Add progress/trend charts to dashboard (rolling average over last N sessions).
3. Export CSV of joint_metrics per report.
