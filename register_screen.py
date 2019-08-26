from tkinter import Tk, Text, Scrollbar, Button, Label, Frame, RIGHT, LEFT, BOTTOM, TOP, NONE, BOTH, Entry
from tkinter.constants import INSERT
import serial
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from threading import Thread, Lock
import logging
import time

logging.basicConfig(level=logging.DEBUG, format='%(message)s',)

root = Tk()
root.wm_title("Console tool")
user_interface = Frame(root)
user_interface.pack(side = LEFT)
visuals = Frame(root)
visuals.pack(side = RIGHT)
content_text = Text(user_interface, wrap='word')

#Taak starten die gaat lezen - eventueel syncrhonizeren om conflict met write te vermijde

def UNLIMITED(val):
    return True

def between(a,b):
    return lambda x: x in range(a,b)

def zeroTo(until):
    return lambda x: x in range(0,until)

class Transformation:
    def __init__(self,regToUser = None,userToReg = None):
        self.reg_to_user = regToUser
        self.user_to_reg = userToReg
    
    def initRegToUser(self,fn):
        self.reg_to_user = fn
        
    def initUserToReg(self, fn):
        self.user_to_reg = fn
        
    def transformRegToUser(self,value):
        if self.reg_to_user == None:
            return value
        return self.reg_to_user(value)
    
    def transformUserToReg(self,value):
        if self.user_to_reg == None:
            return value
        return self.user_to_reg(value)

NO_TRANSFORMATION = Transformation()

class ThreadMessage:
    """
    """
    def __init__(self):
        self.lock = Lock()
        self.write_message = ""
        self.new_message = False

    def write(self, message):
        logging.debug('Waiting to acquire lock')
        self.lock.acquire(True)
        try:
            logging.debug('Acquired lock')
            logging.debug('Message: ' + message)
            self.write_message = message
            self.new_message = True
        finally:
            self.lock.release()
            logging.debug('Released a lock')

class SerialCommander:
    
    def __init__(self):
        self.ser = serial.Serial(#port="/dev/ttyACM0",
                                  baudrate=115200,
                                  bytesize=serial.EIGHTBITS,
                                  parity=serial.PARITY_NONE,
                                  stopbits=serial.STOPBITS_ONE,
                                  timeout=1,
                                  xonxoff=0,
                                  rtscts=0)

    def logCommand(self,command):
        content_text.insert(INSERT, "[COMMAND SEND]: " +  command + "\n")

    def writeCommand(self,command):
        self.logCommand(command)
        self.ser.write(command.encode())
    
    def read(self):
        pass
        
    def write(self):
        pass
    
serialCommander = SerialCommander()

class RegisterEditor:
    def __init__(self,registerId, identification, 
                 defaultValue = 0,
                 transformation = NO_TRANSFORMATION,
                 name = "NO NAME",
                 regRange = UNLIMITED,
                 description = "",
                 writable = True,
                 readable = True):
        self.transformation = transformation
        self.identification = identification
        self.default_value = defaultValue
        self.name = name
        self.regRange = regRange
        self.description = description
        self.reg_id = registerId
        self.writable = writable
        self.readable = readable
        self.serialCommander = serialCommander

    def getRegId(self):
        return self.reg_id
  
    def isWritable(self):
        return self.writable
    
    def isReadable(self):
        return self.readable
    
    def draw(self,container):
        Label(container,text=self.name).pack(side=LEFT, fill=NONE)
        self.entry = Entry(container)
        self.entry.pack(side=LEFT, fill=NONE)
        Button(container, text="write", command = self.write).pack(side=LEFT, fill=NONE)
        Label(container,text=self.description).pack(side=LEFT, fill=NONE)

    def write(self):
        regValue = self.entry.get()
        if regValue.isdigit():
            transformedRegValue = self.transformation.transformUserToReg(float(regValue))
            self.serialCommander.writeCommand(self.identification + str(int(transformedRegValue)) + "\n")


registers = {}

def addReg(newRegister):
    if newRegister.getRegId() in registers.keys():
        raise Exception("Double definition of register") 
    registers[newRegister.getRegId()] = newRegister
    return newRegister

addReg(RegisterEditor(0x3,"Va"
                ,defaultValue = 0
                ,regRange = zeroTo(0xFFF)
                ,name = "Va offset"
                ,description = "offset for voltage measurement phase U"))

addReg(RegisterEditor(0x4,"Vb"
                ,defaultValue = 0
                ,regRange = zeroTo(0xFFF)
                ,name = "Vb offset"
                ,description = "offset for voltage measurement phase V"))

addReg(RegisterEditor(0x5,"Vc"
                ,defaultValue = 0
                ,regRange = zeroTo(0xFFF)
                ,name = "Vc offset"
                ,description = "offset for voltage measurement phase W"))

addReg(RegisterEditor(0x6,"Vd"
                ,defaultValue = 0
                ,regRange = zeroTo(0xFFF)
                ,name = "V supply offset"
                ,description = "offset for voltage measurement supply /DC-bus voltage"))
                                  
addReg(RegisterEditor(0x7, "Ia"
                ,defaultValue = 0x800
                ,regRange = zeroTo(0xFFF)
                ,name = "Ia offset"
                ,description = "Ia offset midpoint for current measurement phase U"))
          
addReg(RegisterEditor(0x8, "Ib"
                ,regRange = zeroTo(0xFFF)    
                ,defaultValue = 0x800,name ="Ib offset"
                ,description = "midpoint for current measurement phase V"))

addReg(RegisterEditor(0x9, "Ic"
                ,regRange = zeroTo(0xFFF)
                ,defaultValue = 0x800  
                ,name ="Ic offset"
                ,description = "midpoint for current measurement phase W"))

addReg(RegisterEditor(0xA, "Is"
                ,regRange = zeroTo(0xFFF)
                ,defaultValue = 0x800
                ,name ="I supply"
                ,description = "midpoint for input current measurement"))

addReg(RegisterEditor(0xB, "Im"
                ,regRange = zeroTo(0xFFF)
                ,defaultValue = 0x800
                ,name ="Imax"
                ,description = "Max current in PID-loop output for current control"
                ,transformation = Transformation(
                                 regToUser = lambda x : float((x - 2048)) * 40.95994
                                ,userToReg = lambda x : int((x * 40.95994) + 2048)))) 

addReg(RegisterEditor(0xC, "Il"
                ,regRange = zeroTo(0xFFF)
                ,defaultValue = 3276
                ,name ="OC_lim"
                ,description = "Max current threshold for safety shutdown"#    0.5 A to 50 A    ± 30.0 A    (value * 40.95994) + 2048 
                ,transformation = Transformation(
                                 regToUser = lambda x : float((x - 2048)) * 40.95994
                                ,userToReg = lambda x : (x * 40.95994) + 2048)))

addReg(RegisterEditor(0xD, "Sd"
                ,regRange = between(-2048,2047)
                ,defaultValue = 0
                ,name ="Id_setpoint"
                ,description = "setpoint direct current (in FOC-mode)"))#    -50.0 A to + 50.0 A        (value * 40.95994)

addReg(RegisterEditor(0xE, "Sq"
                ,regRange = between(-2048,2047)
                ,defaultValue = 0
                ,name ="Iq_setpoint"
                ,description = "setpoint quadrature current (in FOC-mode)"))#    -50.0 A to + 50.0 A        (value * 40.95994)

addReg(RegisterEditor(0xF, "Sp"
                ,regRange = zeroTo(2000)
                ,defaultValue = 0
                ,name ="PWM_setpoint"
                ,description = "setpoint for PWM (in BLDC-mode) sets duty-cycle"))#    0.0 % to 100.0 %        value * 20


addReg(RegisterEditor(0x10,"Su"
                ,regRange = zeroTo(2000)
                ,defaultValue = 0
                ,name ="PWM_set_U"
                ,description = "setpoint for PWM phase U (in DC-mode)"))#    0.0 % to 100.0 %        value * 20

addReg(RegisterEditor(0x11,"Sv"
                ,regRange = zeroTo(2000)
                ,defaultValue = 0
                ,name ="PWM_set_V"
                ,description = "setpoint for PWM phase V (in DC-mode)"))#   0.0 % to 100.0 %        value * 20

addReg(RegisterEditor(0x12,"Sw"
                ,regRange = zeroTo(2000)
                ,defaultValue = 0
                ,name ="PWM_set_W"
                ,description = "setpoint for PWM phase W (in DC-mode)"))#    0.0 % to 100.0 %        value * 20

addReg(RegisterEditor(0x13,"Sr"
                ,regRange = between(-30000,30000)
                ,defaultValue = 0
                ,name ="RPM_setpoint"
                ,description = "setpoint for RPM"))#    -30000 to 30000        value * 1

for reg in registers.values():
    frame = Frame(user_interface)
    reg.draw(frame)
    frame.pack()

def restoreDefaults():
    serialCommander.writeCommand("r")

Button(user_interface,text = "restore defaults",command = restoreDefaults).pack(side=BOTTOM)

def testThreadFunction(threadMessage, message):
    threadMessage.write(message)

Button(user_interface,text = "Test thread",command = lambda: testThreadFunction(threadMessage, message)).pack(side=BOTTOM)

content_text.pack(expand='yes', fill='both')
scroll_bar = Scrollbar(content_text)
content_text.configure(yscrollcommand=scroll_bar.set)
scroll_bar.config(command=content_text.yview)
scroll_bar.pack(side='right', fill='y')

figure1 = plt.Figure(figsize=(6,5), dpi = 100)
ax1 = figure1.add_subplot(111)
scatter = FigureCanvasTkAgg(figure1, visuals)
scatter.get_tk_widget().pack(side=LEFT, fill=BOTH)
ax1.set_xlabel('Some x label')
ax1.set_ylabel('Some y label')

if __name__ == '__main__':
    message = "dummy message"
    threadMessage = ThreadMessage()
    root.mainloop()
