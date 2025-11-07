# import requests, base64, cv2, numpy as np

# r = requests.get("http://0.0.0.0:8000/latest_frame_base64").json()

# if r["ok"]:
#     jpg = base64.b64decode(r["frame_base64"])
#     nparr = np.frombuffer(jpg, np.uint8)
#     img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
#     cv2.imshow("Latest Frame", img)
#     cv2.waitKey(0)

# else:
#     print("Failed to get latest frame")

import cv2

cap = cv2.VideoCapture("http://0.0.0.0:8000/video_feed")

while True:
    ret, frame = cap.read()
    if not ret:
        break
    frame = cv2.resize(frame, (640, 640))
    cv2.imshow("Stream depuis le VPS", frame)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
cv2.destroyAllWindows()
