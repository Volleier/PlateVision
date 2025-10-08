# PlateVision

A simple license plate detection and recognition example project (with front-end and back-end separation).

## Main goal
Automatic License Plate Detection of Vehicles: An Access Control System

### Description
In last few decades, there has been explosive growth in vehicular sector and the number of vehicles passing on the road is
rising exponentially in all the parts of the world. In many countries,increasing number of vehicles are violating the rules of
traffic, ingoing to restricted areas and leading abnormal number of accidents etc. Sometimes, it becomes difficult to identify
vehicle owner who violates traffic rules and drives too fast. From time to time, it is not possible also to catch and punish
those kinds of people because the traffic personal might not be able to retrieve vehicle license number. For the better
management of vehicular traffic and reduce the number of accidents, it is necessary to keep track of vehicles on the basis of
their license plates. For any vehicle to be acknowledged, vehicle license plate plays a main significant role in this active
world. So, in this scenario, to maintain safety and security system, license plate detection plays a major role and we need to 
identify vehicles registration number for finding the vehicle. Therefore, there is a need to develop automatic license plate
detection system of vehicles as one of the solutions to this problem. The main aim of this project is to develop an automatic
system to detect the license plate of vehicles written in Latin.

## Main Content
- Backend: Flask API, responsible for uploading, calling detection/cropping/OCR, and saving results. The main entry point is [`create_app`](backend/App.py) in [backend/App.py].
- Frontend: Vue 3 Vite single-page application, entry file: [frontend/src/main.ts](frontend/src/main.ts).
- Models/Data: The license plate recognition model expects the local model to be placed at `backend/static/models/best.pt`. Uploaded files and results are saved in `backend/static/uploads/` and `backend/static/results/` (these paths are already ignored in .gitignore).