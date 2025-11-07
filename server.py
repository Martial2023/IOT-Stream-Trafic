import asyncio
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, StreamingResponse
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole
import cv2
import numpy as np
import base64


logging.basicConfig(level=logging.INFO)
app = FastAPI()

latest_frame = {
    "frame": None,
    "lock": asyncio.Lock()
}

pcs = set()

async def save_frame(frame_bgr):
    async with latest_frame["lock"]:
        latest_frame["frame"] = frame_bgr

@app.post("/offer")
async def offer(request: Request):
    """
    Reçoit SDP offer depuis le client (PC) et renvoir l'answer.
    Le client doit poster JSON: {"sdp": "<offer sdp>", "type": "offer}
    """

    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    pcs.add(pc)
    logging.info("New PeerConnection created")
    media_sink = MediaBlackhole()

    @pc.on("track")
    def on_track(track):
        logging.info("Track %s received", track.kind)

        if track.kind == "video":
            async def recv_video():
                while True:
                    frame = await track.recv()
                    img = frame.to_ndarray(format="bgr24")

                    await save_frame(img)
            asyncio.ensure_future(recv_video())
        
        @track.on("ended")
        async def on_ended():
            logging.info("Track ended")
            await media_sink.stop()
    
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JSONResponse({
        "sdp": pc.localDescription.sdp,
        "type": pc.localDescription.type
    })

@app.get("/latest_frame_base64")
async def get_latest_frame_base64():
    """
    Pour debug : retourne la dernière frame encodée en JPEG base64 (B64 string).
    Utile pour vérifier que le serveur reçoit bien les frames.
    """
    async with latest_frame["lock"]:
        frame = latest_frame["frame"]
    
    if frame is None:
        return JSONResponse({
            "ok": False,
            "reason": "no_frame_yet"
        })
    
    _, buf = cv2.imencode(".jpg", frame)
    b64 = base64.b64encode(buf.tobytes()).decode("ascii")
    return JSONResponse({
        "ok": True,
        "frame_base64": b64
    })

@app.get("/status")
async def status():
    return {
        "peer_connections": len(pcs)
    }

@app.on_event("shutdown")
async def on_shutdown():
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)


def process_frame(frame):
    return frame

def generate_frames():
    """
    Générateur qui renvoie en continu les frames encodées en JPEG
    pour un flux MJPEG (lecture directe via navigateur ou OpenCV).
    """
    async def frame_generator():
        while True:
            async with latest_frame["lock"]:
                frame = latest_frame["frame"]

            if frame is not None:
                # Encode la frame en JPEG
                frame = cv2.resize(frame, (640, 640))
                frame = process_frame(frame)
                _, buffer = cv2.imencode(".jpg", frame)
                jpg_bytes = buffer.tobytes()
                # Envoie dans le flux
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + jpg_bytes + b"\r\n")
            await asyncio.sleep(0.03)  # environ 30 fps

    return frame_generator()

@app.get("/video_feed")
async def video_feed():
    """
    Diffuse le flux vidéo en continu (MJPEG)
    """
    return StreamingResponse(generate_frames(),
                             media_type="multipart/x-mixed-replace; boundary=frame")