# CricPose AI Pro 🏏🤖

AI-powered cricket fast bowling biomechanics analysis platform that helps bowlers, coaches, academies, and performance analysts evaluate bowling action using computer vision, pose estimation, and advanced performance metrics.

---

# 🚀 Features

## 🎥 Video Analysis
Upload bowling videos and get automated pose-based biomechanical analysis.

Supports:

- Side view bowling videos
- Action phase detection
- Frame-by-frame motion tracking
- Skeleton overlay generation
- Side-by-side processed videos

---

## 📊 Premium Dashboard

Modern sports-tech analytics dashboard with:

- Latest session summary
- Speed score
- Injury risk score
- Progress tracking
- Efficiency score
- Weekly improvements
- Recent sessions history

---

## 📈 Advanced Graphs & Charts

Includes:

1. Shoulder Alignment Box Plot  
2. Pelvis-Shoulder Separation Graph  
3. Trunk Flexion Graph  
4. Front Knee @ Front Foot Contact  
5. Front Knee @ Ball Release  
6. vGRF Force Graph  
7. Ball Speed Graph  
8. Frame-by-Frame Angle Curves  
9. Joint Trajectory Graph  
10. Session Progress Graph  
11. Pro vs User Radar Chart  
12. Risk Heatmap  
13. Symmetry Graph  
14. Release Consistency Graph  

---

## 🏆 Compare With Pro Bowlers

Compare your bowling action against elite bowlers like:

- Jasprit Bumrah
- Dale Steyn
- Brett Lee
- James Anderson
- Pat Cummins
- Mitchell Starc
- Kagiso Rabada

---

## 🤖 AI Pose Engine

Powered by:

- MediaPipe Pose
- OpenCV
- Motion Tracking Algorithms
- Cricket-specific biomechanics calculations

---

## 📄 Report Generation

Generate downloadable performance reports:

- PDF reports
- CSV metrics export
- Session summary reports

---

# 🧠 Key Metrics Measured

- Release speed estimate
- Knee flexion angle
- Shoulder alignment
- Hip-shoulder separation
- Trunk lean
- Stride efficiency
- Rhythm score
- Symmetry balance
- Injury risk probability
- Bowling efficiency index

---

# 🛠 Tech Stack

## Frontend

- React.js
- CRACO
- Tailwind / CSS
- Recharts
- Plotly

## Backend

- FastAPI
- Python
- Uvicorn

## AI / Computer Vision

- MediaPipe
- OpenCV
- NumPy
- Pandas

## Database

- MongoDB

---

# 📂 Project Structure

```bash
cricpose-ai-pro/
│── frontend/
│   ├── src/
│   ├── public/
│   └── package.json
│
│── backend/
│   ├── app/
│   ├── storage/
│   ├── tests/
│   ├── server.py
│   └── requirements.txt
│
└── README.md

⚙️ Installation Guide
1️⃣ Clone Repository
    git clone https://github.com/yourusername/cricpose-ai-pro.git
    cd cricpose-ai-pro

2️⃣ Backend Setup
    cd backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt

Create .env
    MONGO_URL=mongodb://127.0.0.1:27017
    DB_NAME=cricpose
    JWT_SECRET=your_super_secret_key_123456789

Run backend:
    python -m uvicorn server:app --reload --port 8000

3️⃣ Frontend Setup
    cd frontend
    npm install
    npm start

🌐 Run Application
Frontend:
    http://localhost:3000
Backend API Docs:
    http://localhost:8000/docs

🔐 Security Features
    JWT Authentication
    Protected Routes
    Secure File Uploads
    Token Based Sessions
    CORS Enabled API

📌 Use Cases
    Fast Bowlers
    Cricket Academies
    Strength & Conditioning Coaches
    Injury Rehab Monitoring
    Performance Labs
    Talent Scouting
    Coaching Institutes

🚀 Future Improvements
    Real Ball Tracking
    Accurate Speed Detection
    Multi-Camera 3D Analysis
    Mobile App Version
    Live Camera Capture
    Coach Dashboard
    AI Bowling Suggestions
    Recruitment Scoring Engine

👨‍💻 Developed By
    Ritesh