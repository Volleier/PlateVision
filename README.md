\*# PlateVision

A simple license plate detection and recognition example project (with front-end and back-end separation).

## Main goal

Automatic License Plate Detection of Vehicles: An Access Control System

### Description

In last few decades, there has been explosive growth in vehicular sector and the number of vehicles passing on the road is
rising exponentially in all the parts of the world. In many countries, increasing number of vehicles are violating the rules of
traffic, going into restricted areas and causing an abnormal number of accidents etc. Sometimes, it becomes difficult to identify
vehicle owner who violates traffic rules and drives too fast. From time to time, it is not possible also to catch and punish
those kinds of people because the traffic personnel might not be able to retrieve vehicle license number. For better
management of vehicular traffic and to reduce the number of accidents, it is necessary to keep track of vehicles on the basis of
their license plates. For any vehicle to be identified, the vehicle license plate plays a major role in this modern
world. So, in this scenario, to maintain safety and security, license plate detection plays a major role and we need to
identify vehicle registration numbers for finding the vehicle. Therefore, there is a need to develop an automatic
license plate detection system for vehicles as one of the solutions to this problem. The main aim of this project is to develop an automatic
system to detect the license plate of vehicles written in Latin.

## Main Content

- Backend: Flask API, responsible for uploading, calling detection/cropping/OCR, and saving results. The main entry point is [`create_app`](backend/App.py) in [backend/App.py].
- Frontend: Vue 3 Vite single-page application, entry file: [frontend/src/main.ts](frontend/src/main.ts).
- Models/Data: The license plate recognition model expects the local model to be placed at `backend/static/models/best.pt`. Uploaded files and results are saved in `backend/static/uploads/` and `backend/static/results/` (these paths are already ignored in .gitignore).

## workflow

```
┌─────────────────────────────────────────────────────────────┐
│ 1. Frontend uploads image │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ 2. receive.py::upload() │
│ - Generate unique file_id (ULID) │
│ - Save to uploads/{file_id}.jpg │
│ - Submit worker task │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ 3. Worker: processing_image(file_id) │
│ ├─ detector_step(file_id) │
│ │ └─ Save: detector/{file_id}_pred.jpg │
│ ├─ extractor_step(file_id) │
│ │ └─ Save: extractor/{file_id}_crop_0.jpg │
│ └─ reader_step(file_id) │
│   └─ Save: reader/{file_id}_crop_0_pred.jpg │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ 4. _task_done_callback() │
│ - Extract reader_images from the results │
│ - Filter images that contain the file_id │
│ - Store into _jobs[job_id]["result_image"] │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ 5. Frontend polls /api/tasks/{job_id} │
│ - status=pending → continue waiting │
│ - status=done → obtain the file_id │
└─────────────────────────────────────────────────────────────┘
↓
┌─────────────────────────────────────────────────────────────┐
│ 6. Frontend calls /api/send/{file_id} │
│ - send.py reads the result_image path from _jobs │
│ - Returns the corresponding image file │
└─────────────────────────────────────────────────────────────┘
```
