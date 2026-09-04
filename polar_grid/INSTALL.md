# PolarGrid AI - Installation Guide

## Quick Start (Windows)

### Step 1: Delete Old Files
If you have an existing `polar_grid` folder, **delete it completely**.

### Step 2: Download & Extract
1. Download `polar_grid.zip` from the workspace
2. Extract to your Desktop (or any folder WITHOUT spaces in the path)
   - ✅ Good: `C:\Users\YourName\Desktop\polar_grid`
   - ❌ Bad: `C:\Users\YourName\OneDrive\Desktop\New folder\polar_grid`

### Step 3: Install Dependencies
Open Command Prompt in the `polar_grid` folder and run:
```cmd
pip install -r requirements.txt
```

### Step 4: Run the Server
Double-click `run.bat` OR run:
```cmd
python backend/main.py
```

### Step 5: Open Dashboard
Open your browser and go to:
```
http://localhost:8000
```

---

## Troubleshooting

### Issue: "UnicodeDecodeError: 'charmap' codec can't decode"
**Fix:** This is already fixed in the new zip. Delete old files and use the new zip.

### Issue: "ModuleNotFoundError: No module named 'fastapi'"
**Fix:** Run `pip install -r requirements.txt`

### Issue: Dashboard loads but shows "--" for all values
**Fix:** 
1. Check the Command Prompt for errors
2. Open browser console (F12) and check for errors
3. Try the health check: http://localhost:8000/api/health
4. If that works, try: http://localhost:8000/api/stations

### Issue: Port 8000 already in use
**Fix:** 
- Close any other servers running on port 8000
- Or edit `backend/main.py` and change `port=8000` to `port=8001`

### Issue: Slow startup (30+ seconds)
**Fix:** Normal! The system trains ML models on first run. Subsequent runs are faster.

---

## Verification

After starting the server, you should see:
```
==================================================
PolarGrid AI: Initializing system...
==================================================
  Loading Maitri (Antarctica)...
    8760 hours of data generated
  Loading Bharati (Antarctica)...
    8760 hours of data generated
  Loading Himadri (Arctic)...
    8760 hours of data generated

  Training AI Load Forecaster...
    MAE: 9.26 kW, R2: 0.9532
  Training Renewable Energy Forecaster...
    Done.

  Project root: C:\Users\YourName\Desktop\polar_grid
  Stations loaded: 3
  Model trained: True
==================================================
System initialized successfully!

INFO:     Started server process [XXXX]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
```

Then in your browser, you should see:
- Real-time KPIs with actual values (not "--")
- Charts with data
- Timestamp showing current time (not "Loading...")

---

## File Structure
```
polar_grid/
── backend/
│   ├── main.py              ← Server (run this)
│   ├── data_simulator.py    ← Data generation
│   ├── ml_models.py         ← AI models
│   ── optimizer.py         ← Energy optimization
├── frontend/
│   ├── templates/
│   │   └── index.html       ← Dashboard
│   └── static/
│       ├── style.css        ← Styling
│       └── app.js           ← JavaScript
├── models/
│   └── forecaster.pkl       ← Trained model (auto-generated)
── requirements.txt         ← Python dependencies
├── run.bat                  ← Windows launcher
├── README.md                ← Full documentation
└── SOLUTION.md              ← Technical details
```

---

## System Requirements
- Python 3.8 or higher
- Windows 10/11, macOS, or Linux
- 4GB RAM minimum
- Internet connection (for pip install only)

---

## Support

If you still have issues:
1. Check the Command Prompt for error messages
2. Open browser console (F12) for JavaScript errors
3. Try the health check endpoint: http://localhost:8000/api/health
4. Make sure you're using the NEW zip (not the old one)

Good luck with the hackathon! 🏆
