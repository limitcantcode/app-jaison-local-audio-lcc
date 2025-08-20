import websockets
import json
import base64
import asyncio
import os
import datetime
import time
import aiohttp

from utils.device import DeviceManager

class Responder:
    def __init__(self):
        self.JAISON_WS_SERVER = os.getenv("JAISON_WS_SERVER")
        self.JAISON_HTTP_SERVER = os.getenv("JAISON_HTTP_SERVER")
        self.USERNAME = os.getenv("USER_NAME")

        self.current_response_job = None
        self.current_pending = False

        self.last_audio_job = None
        self.audio_start_time = 0
        self.audio_duration = 0
        self.audio_gen_finished = True

    async def event_loop(self, dm: DeviceManager):
        print("Event loop starting...")
        while True:
            try:
                async with websockets.connect(self.JAISON_WS_SERVER) as ws:
                    print("Connected to jaison-core websocket server")
                    while True:
                        data = json.loads(await ws.recv())
                        event, status = data[0], data[1]
                        response = event.get("response", {})
                        job_id = response.get('job_id')
                        result = response.get("result", {})
                        
                        if job_id is None:
                            continue
                        
                        match event.get("message", ""):
                            case "response":
                                if "audio_bytes" in result:
                                    if self.current_response_job == job_id:
                                        self.current_pending = False
                                    if self.last_audio_job != job_id:
                                        self.last_audio_job = job_id
                                        self.audio_start_time = time.perf_counter_ns()
                                        self.audio_duration = 0
                                        self.audio_gen_finished = False
                                    
                                    ab = base64.b64decode(result['audio_bytes'])
                                    sr = result['sr']
                                    sw = result['sw']
                                    ch = result['ch']
                                    
                                    dm.write_enqueue(ab,sr,sw,ch)
                                    self.audio_duration += len(ab)*1000000000/(sw*ch*sr)
                                    
                                if response.get("finished", False):
                                    self.audio_gen_finished = True
                            case _:
                                pass
            except OSError:
                print("Server closed suddenly. Attempting reconnect in 5 seconds")
                await asyncio.sleep(5)
            except Exception as err:
                print("Event listener encountered an error: {}".format(str(err)))
                
    async def listen(self, ab: bytes, sr: int, sw: int, ch: int):
        await self.cancel_pending()
        await self.add_convo_audio(ab, sr, sw, ch)
                
    async def cancel_pending(self):
        if self.current_response_job and self.current_pending:
            async with aiohttp.ClientSession() as session:
                async with session.delete(
                    self.JAISON_HTTP_SERVER+'/api/job',
                    headers={"Content-type":"application/json"},
                    json={
                        "job_id": self.current_response_job,
                        "reason": "Preventing interruption in conversation"
                    }
                ) as response:
                    pass
            
        self.current_pending = False
        
                
    async def add_convo_audio(self, ab: bytes, sr: int, sw: int, ch: int):
        async with aiohttp.ClientSession() as session:
            async with session.post(
                self.JAISON_HTTP_SERVER+'/api/context/conversation/audio',
                headers={"Content-type":"application/json"},
                json={
                    "user": self.USERNAME,
                    "timestamp": int(datetime.datetime.now().timestamp()),
                    "audio_bytes": base64.b64encode(ab).decode('utf-8'),
                    "sr": sr,
                    "sw": sw,
                    "ch": ch,
                }
            ) as response:
                if response.status >= 300:
                    print("Failed to add to convo: {}".format(await response.text))
            
    async def respond(self) -> bool:
        '''
        Returns whether it successfully reqeusted a response or not.
        
        If not, then may be a server error or not sent to avoid response clashing
        '''
        print("Attempting to respond")
        if self.audio_start_time+self.audio_duration < time.perf_counter_ns() and self.audio_gen_finished:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.JAISON_HTTP_SERVER+'/api/response',
                    headers={"Content-type":"application/json"},
                    json={"include_audio": True}
                ) as response:
                    if response.status >= 300:
                        print("Failed to request response: {}".format(response.text))
                        return False
                    else:
                        parsed_response = await response.json()
                        self.current_response_job = parsed_response['response']['job_id']
                        self.current_pending = True
                        print("Response request successful")
                        return True
        else:
            print("Can't interrupt current action: is_done_playing({}) is_finished_generating({})".format(self.audio_start_time+self.audio_duration < time.perf_counter_ns(), self.audio_gen_finished) )
            print("Current time: {}".format(time.perf_counter_ns()))
            print("Expected finish: {}".format(self.audio_start_time+self.audio_duration))
            return False