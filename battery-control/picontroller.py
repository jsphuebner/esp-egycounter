class PiController:
    def __init__(self, kp, ki, minimum = 0, maximum = 0):
        self.kp = kp
        self.ki = ki
        self.errsum = 0
        self.minOutput = 0
        self.setMinMax(minimum, maximum)
        
    def setMinMax(self, minimum, maximum):
        self.minimum = minimum
        self.maximum = maximum
        if self.ki != 0:
            self.minint = minimum / self.ki
            self.maxint = maximum / self.ki
        else:
            self.minint = 0
            self.maxint = 0
        
    def setMinOutput(self, minOut):
        self.minOutput = minOut
        
    def resetIntegrator(self):
        self.errsum = 0

    def run(self, currentValue, targetValue):
        err = currentValue - targetValue
        self.errsum = self.errsum + err
        self.errsum = min(self.maxint, self.errsum)
        self.errsum = max(self.minint, self.errsum)
        
        y = self.kp * err + self.ki * self.errsum
        y = min(self.maximum, y)
        y = max(self.minimum, y)
        
        if abs(y) < self.minOutput:
            y = 0
            self.errsum = 0
            
        return y
