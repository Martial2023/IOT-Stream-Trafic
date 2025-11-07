import asyncio
import argparse
import cv2
import numpy as np
import aiohttp
from aiortc import RTCPeerConnection, RTCSessionDescription, VideoStreamTrack, RTCConfiguration, RTCIceServer
from av import VideoFrame
import time


class CameraVideoTrack(VideoStreamTrack):
    """
    Track qui utilise OpenCV pour lire la webcam et renvoyer des frames.
    """

    def __init__(self, width=640, height=640, fps=30):
        super().__init__()
        self.cap = cv2.VideoCapture("vid2.mp4")
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, width)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, height)
        self.fps = fps
        self._start = time.time()
    
    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        if not ret:
            raise Exception("Could not read frame from camera")
        
        video_frame = VideoFrame.from_ndarray(frame, format="bgr24")
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

async def run(pc, server_url, stun_servers):
    ice_servers = [RTCIceServer(urls=stun_servers)] if stun_servers else []

    track = CameraVideoTrack()
    pc.addTrack(track)

    offer = await pc.createOffer()
    await pc.setLocalDescription(offer)

    async with aiohttp.ClientSession() as session:
        offer_payload = {
            "sdp": pc.localDescription.sdp,
            "type": pc.localDescription.type
        }
        async with session.post(server_url + "/offer", json=offer_payload) as resp:
            if resp.status != 200:
                print("Failed to get answer from server: ", resp.text())
                return
            answer = await resp.json()
    
    await pc.setRemoteDescription(RTCSessionDescription(sdp=answer["sdp"], type=answer["type"]))
    print("WebRTC connection established. Streaming video...")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--server", required=True, help="URL du VPS, ex: http://vps_address:port")
    parser.add_argument("--stun", default="stun:stun.l.google.com:19302", help="Serveur STUN à utiliser")
    args = parser.parse_args()

    pc = RTCPeerConnection()
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(run(pc, args.server, [args.stun]))
    finally:
        loop.run_until_complete(pc.close())