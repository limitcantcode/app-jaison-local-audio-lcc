import time

class Timer:
    ONE_SECOND = 1000000000
    
    def __init__(self):
        self.next_time_ns = 0
        
    def delay(self, delay_ns) -> int:
        self.next_time_ns = time.perf_counter_ns() + delay_ns
        
    def is_next(self) -> bool:
        return time.perf_counter_ns() >= self.next_time_ns