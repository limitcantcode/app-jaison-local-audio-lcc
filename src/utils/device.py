import pyaudio
import os
import numpy as np

class DeviceManager:
    INPUT_SAMPLE_WIDTH = 2
    INPUT_CHANNELS = 1
    INPUT_SAMPLE_RATE = 16000
    INPUT_CHUNK = int(INPUT_SAMPLE_RATE / 10)
    INPUT_SAMPLES = 512
    
    OUTPUT_SAMPLE_RATE = 48000
    OUTPUT_SAMPLE_WIDTH = 2
    OUTPUT_CHANNELS = 2
    MAX_OUT = 8192
    
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        
        self.print_devices()
        
        self.input_stream = self.audio.open(
            format=self.audio.get_format_from_width(self.INPUT_SAMPLE_WIDTH,unsigned=False),
            channels=self.INPUT_CHANNELS,
            rate=self.INPUT_SAMPLE_RATE,
            input=True,
            input_device_index=self.get_input_device_index(),
            frames_per_buffer=self.INPUT_CHUNK
        )
        self.output_stream = self.audio.open(
            format=self.audio.get_format_from_width(self.OUTPUT_SAMPLE_WIDTH,unsigned=False),
            channels=self.OUTPUT_CHANNELS,
            rate=self.OUTPUT_SAMPLE_RATE,
            output=True,
            output_device_index=self.get_output_device_index(),
            frames_per_buffer=self.MAX_OUT
        )
        
        self.audio_out_buf = b""
        
    def print_devices(self) -> None:
        # List devices
        print("Available devices:")
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            print(f"{i}: {info['name']}")
        
    def get_input_device_index(self) -> int:     
        # Choose device
        device_name = os.getenv("INPUT_DEVICE_NAME")
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if device_name.lower() in info['name'].lower() and info['maxInputChannels'] > 0:
                return i
        raise Exception("No input device with name {}".format(device_name))
    
    def get_output_device_index(self) -> int:     
        # Choose device
        device_name = os.getenv("OUTPUT_DEVICE_NAME")
        for i in range(self.audio.get_device_count()):
            info = self.audio.get_device_info_by_index(i)
            if device_name.lower() in info['name'].lower() and info['maxOutputChannels'] > 0:
                return i
        raise Exception("No output device with name {}".format(device_name))
    
    def read(self) -> np.ndarray:
        audio_chunk = self.input_stream.read(self.INPUT_SAMPLES, exception_on_overflow=False)
        return np.frombuffer(audio_chunk, np.int16)
    
    def write(self) -> None:
        audio_opt = self.audio_out_buf[:self.MAX_OUT]
        self.audio_out_buf = self.audio_out_buf[self.MAX_OUT:]
        if len(audio_opt) > 0:
            for i in range(len(audio_opt),self.MAX_OUT):
                audio_opt += b"\x00" # pad with silence
            self.output_stream.write(audio_opt)
        
            
    def process_buffers(self) -> np.ndarray:
        self.write()
        return self.read()
    
    def write_enqueue(self, ab: bytes, sr: int, sw: int, ch: int) -> None:
        audio_opt = self.format_audio_for_output(ab, sr, sw, ch)
        self.audio_out_buf += audio_opt
         
    def format_audio_for_output(self, ab: bytes, sr: int, sw: int, ch: int) -> bytes:
        dtype = np.dtype(f'i{sw}')
        audio_array = np.frombuffer(ab, dtype=dtype) # parse bytes
        audio_array = (audio_array.reshape([int(audio_array.shape[0]/ch), ch])/ch).sum(1) # average across channels into 1 channel
        audio_array = np.interp(np.arange(0, len(audio_array), float(sr)/self.OUTPUT_SAMPLE_RATE), np.arange(0, len(audio_array)), audio_array) # resample
        audio_array = audio_array.flatten().repeat(2) # Discord wants 2 channel audio
        match sw: # Rescale volume
            case 1:
                audio_array = audio_array.astype(np.int16) * 256
            case 2:
                audio_array = audio_array.astype(np.int16)
            case 4:
                audio_array = (audio_array / 65536).astype(np.int16)
            case _:
                raise Exception("Invalid sample width given: {src_sw}")

        return bytes(audio_array.tobytes())