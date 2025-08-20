from dotenv import load_dotenv
load_dotenv()

import asyncio
import os

from utils.device import DeviceManager
from utils.vad import VAD
from utils.timer import Timer
from utils.response import Responder


async def main_with_input():
    vad = VAD()
    pause_timer = Timer()
    respond_timer = Timer()
    idle_timer = Timer()
    dm = DeviceManager()
    responder = Responder()
    
    event_task = asyncio.create_task(responder.event_loop(dm))
    
    should_respond = False
    idle_timer.delay(int(os.getenv("IDLE_TIME"))*idle_timer.ONE_SECOND)
    pause_timer.delay(pause_timer.ONE_SECOND)
    
    print("Recording started")
    while True:
        await asyncio.sleep(0)
        ab = dm.process_buffers()
        
        try:
            is_detected = vad.feed(ab)
        except:
            is_detected = False

        if is_detected and responder.current_pending:
            await responder.cancel_pending()
            
        if (not is_detected) and pause_timer.is_next():
            ab = vad.extract()
            if len(ab) > 0:
                asyncio.create_task(responder.listen(ab, dm.INPUT_SAMPLE_RATE, dm.INPUT_SAMPLE_WIDTH, dm.INPUT_CHANNELS))
                should_respond= True
                respond_timer.delay(respond_timer.ONE_SECOND)
            pause_timer.delay(pause_timer.ONE_SECOND)
            
        if should_respond and respond_timer.is_next():
            asyncio.create_task(responder.respond())
            should_respond = False
            idle_timer.delay(int(os.getenv("IDLE_TIME"))*idle_timer.ONE_SECOND)
            
        if (not is_detected) and idle_timer.is_next():
            asyncio.create_task(responder.respond())
            idle_timer.delay(int(os.getenv("IDLE_TIME"))*idle_timer.ONE_SECOND)
            
        if is_detected:
            should_respond = False
            pause_timer.delay(pause_timer.ONE_SECOND)
            idle_timer.delay(int(os.getenv("IDLE_TIME"))*idle_timer.ONE_SECOND)

asyncio.run(main_with_input())