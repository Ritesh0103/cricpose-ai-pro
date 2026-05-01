# CricPose Bowling Analysis Pipeline

This project currently uses FastAPI in `backend/server.py` rather than Flask. The new pipeline is integrated into that backend so it works with the existing auth, upload, and frontend API style.

## Data Layout

Put Kaggle cricket bowling clips or images here:

```text
data/
  raw_videos/
    pro_bowlers/
      jasprit_bumrah/
      mitchell_starc/
      mohammed_shami/
    users/
  processed_frames/
  keypoints/
  datasets/
  profiles/
  static/videos/
```

You can override the data folder with:

```bash
export CRICPOSE_DATA_DIR=/absolute/path/to/data
```

## What The Pipeline Does

1. Loads all supported files from `data/raw_videos`.
2. Extracts sampled frames, resizes them to `640x640`, and stores them in `data/processed_frames`.
3. Runs MediaPipe Pose and exports shoulder, elbow, wrist, hip, knee, and ankle keypoints to `data/keypoints`.
4. Extracts bowling features:
   - `arm_angle_deg`
   - `release_angle_deg`
   - `runup_speed_normalized_per_s`
   - `knee_bend_deg`
   - `spine_alignment_deg`
5. Creates mandatory per-video CSVs in `data/datasets/{video_id}.csv`.
6. Builds per-bowler profiles in `data/profiles/{bowler}.json` from CSV statistics.
7. Learns metric weights from variance across professional bowler profiles.
8. Compares a user upload against selected bowler profiles and returns UI-ready JSON plus static video URLs.

## Backend Files

Core modules:

```text
backend/app/pipeline/preprocessing.py
backend/app/pipeline/pose_detector.py
backend/app/pipeline/biomechanics.py
backend/app/services/bowling_pipeline_service.py
backend/app/routes/bowling_pipeline.py
```

Path settings live in:

```text
backend/app/core/config.py
```

## Run End To End

Install backend dependencies:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Start the backend:

```bash
uvicorn server:app --reload --host 0.0.0.0 --port 8000
```

Sign in through the existing app or call the guest endpoint, then use the returned bearer token.

Process all raw videos into keypoints and CSV datasets:

```bash
curl -X POST "http://localhost:8000/api/pipeline/process-all?sample_fps=8" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Build data-driven bowler profiles:

```bash
curl -X POST "http://localhost:8000/api/pipeline/build-profiles" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

Analyze a user bowling video:

```bash
curl -X POST "http://localhost:8000/api/pipeline/analyze?sample_fps=8" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -F 'selected_bowlers=["jasprit_bumrah","mitchell_starc"]' \
  -F "file=@/path/to/user_bowling.mp4"
```

Check configured paths:

```bash
curl "http://localhost:8000/api/pipeline/data-layout" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

## Example JSON Output

```json
{
  "summary": {
    "overall_score": 86.5,
    "efficiency": 82.4,
    "balance": 91.2,
    "consistency": 78.7
  },
  "radar": {
    "labels": ["Release Angle", "Front Knee Brace", "Shoulder Alignment"],
    "datasets": [{"name": "You", "values": [84.1, 79.2, 90.0]}]
  },
  "metrics": [],
  "time_series": {},
  "insights": [],
  "injury_risk": {"score": 0, "factors": []},
  "events": {"BFC": 12, "FFC": 24, "RELEASE": 31}
}
```

## Important Notes

- Use only clean professional bowling clips in `data/raw_videos/pro_bowlers/{bowler}` before building profiles. Bad examples will make that bowler profile noisy.
- Run-up speed and release speed are single-camera normalized estimates. For real m/s, add camera calibration with pitch markers or radar ground truth.
- Comparisons, weights, distributions, insight severity, and UI scores are derived from the CSV/profile statistics, not fixed benchmark numbers.
- The existing `/api/analysis/upload` endpoint remains available and already produces richer dashboard metrics and overlay assets.
