from tkinter import Tk, Text, Scrollbar, Button, Label, Frame, RIGHT, LEFT, X, BOTTOM, TOP, NONE, BOTH, Entry, StringVar
from tkinter.constants import INSERT
import serial
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from threading import Thread, Lock
import logging
import time
import numpy as np
from filtering import Filter

logging.basicConfig(level=logging.DEBUG, format='%(message)s',)

root = Tk()
root.wm_title("Console tool")
user_interface = Frame(root)
user_interface.pack(side = LEFT)
visuals = Frame(root)
visuals.pack(side = RIGHT)

upper_visuals = Frame(visuals)
upper_visuals.pack(side=TOP)
lower_visuals = Frame(visuals)
lower_visuals.pack(side=TOP)
bottom_displays = Frame(visuals)
bottom_displays.pack(side=TOP)

content_text = Text(user_interface, wrap='word')

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

class Data:
    """
    Class that abstract the binary storage approach. If one used for writing data to, the other is 
    used to read data from. If the first is full, a switch is made between the two.
    """
    def __init__(self, size=(300, 18)):
        self.buffer1 = np.empty(size)
        self.buffer2 = np.empty(size)
        self.validToRead1 = False
        self.__buffer_index = 0
        self.__buffer_index_max = size[0]

    def push_row(self, array):
        """
        Push an row of data onto the available buffer
        """
        if self.validToRead1:
            self.buffer2[self.__buffer_index, :] = array
        else:
            self.buffer1[self.__buffer_index, :] = array
        self.__buffer_index += 1

        if self.__buffer_index == self.__buffer_index_max:
            self.validToRead1 = not self.validToRead1
            self.__buffer_index = 0
            root.event_generate("<<GeneratePlots>>", when="tail")
            #logging.debug("buffer full")

    def flush(self):
        """
        Return the valid buffer for further user
        """
        if self.validToRead1:
            return self.buffer1
        else:
            return self.buffer2


class ThreadMessage:
    """
    Class supports safe exchange of data between multiple threads.
    """
    def __init__(self):
        self.lock = Lock()
        self.write_message = ""
        self.new_message = False
        self.halt_thread = False
        self.data = Data()

    def write(self, message):
        self.lock.acquire(True)
        try:
            self.write_message = message
            self.new_message = True
        finally:
            self.lock.release()

    def toggle_new_message(self):
        with self.lock:
            self.new_message = not self.new_message

    def writeBuffer(self, array):
        #NOTE: is lock necessary?
        with self.lock:
            self.data.push_row(array)

    def readBuffer(self):
        #NOTE: is lock necessary?
        with self.lock:
            return self.data.flush()

class SerialCommandConsumer:
    """
    Class that handles a single instance of a ThreadMessage in the second thread.
    """
    def __init__(self):
        pass

    def __call__(self, threadMessage=None):
        serialConnection = serial.Serial(port="/dev/rfcomm3",
                                baudrate=115200,
                                bytesize=serial.EIGHTBITS,
                                parity=serial.PARITY_NONE,
                                stopbits=serial.STOPBITS_ONE,
                                timeout=1,
                                xonxoff=0,
                                rtscts=0)
        if isinstance(threadMessage, ThreadMessage):
            while not threadMessage.halt_thread:
                if not threadMessage.new_message:
                    #TODO: check for timeout of readline
                    line = serialConnection.readline().decode('ASCII')
                    dummy = self.handleValueErrors([item.strip() for item in line.split(",")])
                    if not dummy[0] or len(dummy[1]) != 18:
                        # discard line of a ValueError occurs
                        # or if length is not correct
                        continue
                    
                    logging.debug(dummy[1])
                    threadMessage.writeBuffer(dummy[1])
                    continue
                else:
                    serialConnection.write(threadMessage.write_message)
                    threadMessage.toggle_new_message()
                #time.sleep(0.005)
            else:
                logging.info('Received halt condition')

    def handleValueErrors(self, raw_array):
        valid = True
        converted_array = []
        for item in raw_array:
            try:
                converted_array.append(int(item))
            except ValueError:
                valid = False
                break
        return (valid, converted_array)



class SerialCommandProducer:
    """
    Class that handles a single instance of a ThreadMessage in the primary thread.
    """

    def __init__(self, threadMessage=None):
        self.threadMessage=threadMessage

    def write(self, command):
        threadMessage.write(command)
    

class SerialCommander:
    
    def __init__(self, threadProducer=None):
        self.threadProducer = threadProducer

    def logCommand(self,command):
        content_text.insert(INSERT, "[COMMAND SEND]: " +  command + "\n")

    def writeCommand(self,command):
        self.logCommand(command)
        self.threadProducer.write(command.encode())
    
    def read(self):
        pass
        
    def write(self):
        pass

threadMessage = ThreadMessage() #used as a global
serialCommander = SerialCommander(SerialCommandProducer(threadMessage))

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

addReg(RegisterEditor(0x50,"Mc"
                ,defaultValue = 0
                ,regRange = zeroTo(8)
                ,name = "OUTPUT CONTROL: \nctrl_mode"
                ,description = "(0)=PWM; (1)=RPM; (2)=current; (3)=FOC"))

addReg(RegisterEditor(0xD, "Sd"
                ,regRange = between(-2048,2047)
                ,defaultValue = 0
                ,name ="Id_setpoint"
                ,description = "setpoint direct current (in FOC-mode)"#    -50.0 A to + 50.0 A        (value * 40.95994)
                ,transformation=Transformation(
                    regToUser=lambda x: float(x / 40.95994),
                    userToReg=lambda x: (x * 40.95994))))

addReg(RegisterEditor(0xE, "Sq"
                ,regRange = between(-2048,2047)
                ,defaultValue = 0
                ,name ="Iq_setpoint"
                ,description = "setpoint quadrature current (in FOC-mode)"#    -50.0 A to + 50.0 A        (value * 40.95994)

                ,transformation=Transformation(
                    regToUser=lambda x: float(x / 40.95994),
                    userToReg=lambda x: (x * 40.95994))))#temp RMS

addReg(RegisterEditor(0xF, "Sp"
                ,regRange = zeroTo(2000)
                ,defaultValue = 0
                ,name ="PWM_setpoint"
                ,description = "Set duty-cycle 0.0% to 100.0%"#    0.0 % to 100.0 %        value * 20
                ,transformation=Transformation(
                    regToUser=lambda x: float(x) *20,
                    userToReg=lambda x: (x * 20))))#temp RMS

addReg(RegisterEditor(0x13,"Sr"
                ,regRange = between(-30000,30000)
                ,defaultValue = 0
                ,name ="RPM_setpoint"
                ,description = "setpoint for RPM"))#    -30000 to 30000        value * 1

addReg(RegisterEditor(0x15,"Sf"
                ,regRange = zeroTo(2000)
                ,defaultValue = 1953
                ,name ="ac_freq"
                ,description = "Set frequency of the AC output"# 0.0% to 100.0% valye *20
                ,transformation=Transformation(
                    regToUser=lambda x: float(97656 /x),
                    userToReg=lambda x: (97656/x))))

addReg(RegisterEditor(0x20,"Td"
                ,regRange = between(10,100)
                ,defaultValue = 32
                ,name ="dead_time"
                ,description = "Set output dead time (ns)"
                ,transformation=Transformation(
                    regToUser=lambda x: float(x*10),
                    userToReg=lambda x: (x/10))))

addReg(RegisterEditor(0x22,"Ts"
                ,regRange = zeroTo(10000)
                ,defaultValue = 500
                ,name ="slope"
                ,description = "set PWM rate of change in % per us"
                ,transformation=Transformation(
                    regToUser=lambda x: float(x) *1, #not defined yet
                    userToReg=lambda x: (x*1))))

addReg(RegisterEditor(0x23,"Tp"
                ,regRange = between(-1023, 1023)
                ,defaultValue = 32
                ,name ="phase_shift"
                ,description = "set phase-shift in degrees"
                ,transformation=Transformation(
                    regToUser=lambda x: float(x) *0.3525625,
                    userToReg=lambda x: (x/ 0.3525626))))

addReg(RegisterEditor(0xB, "Im"
                ,regRange = zeroTo(0xFFF)
                ,defaultValue = 0x800
                ,name ="Imax"
                ,description = "Max current in PID-loop output for current control"
                ,transformation = Transformation(
                    regToUser = lambda x : float((x - 2048)) * 40.95994
                    ,userToReg = lambda x : int((x * 40.95994) + 2048)))) 

addReg(RegisterEditor(0x30, "Lp"
                ,regRange = zeroTo(2047)
                ,defaultValue = 60
                ,name ="CONTROL LOOPS: \n P_gain_0"
                ,description = "Kp in RPM control-loop (0 to 10)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x / 20.47)
                    ,userToReg = lambda x : (x * 20.47)))) 

addReg(RegisterEditor(0x31, "Li"
                ,regRange = zeroTo(2047)
                ,defaultValue = 40
                ,name ="I_gain_0"
                ,description = "Ki in RPM control-loop (0 to 10)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x / 20.47)
                    ,userToReg = lambda x : (x * 20.47)))) 

addReg(RegisterEditor(0x32, "Ld"
                ,regRange = zeroTo(2047)
                ,defaultValue = 0
                ,name ="d_gain_0"
                ,description = "Kd in rpm control-loop (0 to 10)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x / 20.47)
                    ,userToReg = lambda x : (x * 20.47)))) 
                    
addReg(RegisterEditor(0x33, "Lf"
                ,regRange = between(125, 6250000)
                ,defaultValue = 62500
                ,name ="PID_0_f"
                ,description = "RPM control loop frequency (Hz)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(62500000 / x)
                    ,userToReg = lambda x : (62500000/x)))) 

addReg(RegisterEditor(0x34, "Lq"
                ,regRange = zeroTo(2047)
                ,defaultValue = 60
                ,name ="P_gain_1"
                ,description = "Kp in current source control-loop (0 to 10)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x /20.47)
                    ,userToReg = lambda x : (x *20.47)))) 

addReg(RegisterEditor(0x35, "Lr"
                ,regRange = zeroTo(2047)
                ,defaultValue = 40
                ,name ="I_gain_1"
                ,description = "Ki in current source control-loop (0 to 10)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x /20.47)
                    ,userToReg = lambda x : (x *20.47)))) 

addReg(RegisterEditor(0x36, "Ls"
                ,regRange = zeroTo(2047)
                ,defaultValue = 0
                ,name ="D_gain_1"
                ,description = "Kd in current source control-loop (0 to 10)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x /20.47)
                    ,userToReg = lambda x : (x *20.47)))) 

addReg(RegisterEditor(0x37, "Lg"
                ,regRange = between(125, 6250000)
                ,defaultValue = 1250 # 50 kHz
                ,name ="PID_1_f"
                ,description = "current source control loop frequency (Hz)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(62500000 / x)
                    ,userToReg = lambda x : (62500000 / x)))) 

addReg(RegisterEditor(0x42, "Et"
                ,regRange = zeroTo(2047)
                ,defaultValue = 2344
                ,name ="LIMITS: \n temp_limit"
                ,description = "Temperature limit MOSFETs (deg C)"
                ,transformation = Transformation(
                    regToUser = lambda x : float(x - 1940/3.85333)
                    ,userToReg = lambda x : (x*3.85333)+1940))) 

addReg(RegisterEditor(0xC, "Il"
                ,regRange = zeroTo(0xFFF)
                ,defaultValue = 3276
                ,name ="OC_lim_i"
                ,description = "Over-current (input) protection (A)"
                ,transformation = Transformation(
                    regToUser = lambda x : float((x - 2048)) * 40.95994
                    ,userToReg = lambda x : (x * 40.95994) + 2048)))

addReg(RegisterEditor(0x7, "Ia"
                ,defaultValue = 4000
                ,regRange = zeroTo(0xFFF)
                ,name = "OC_lim_o"
                ,description = "Over-current (output) protection (A)"
                ,transformation = Transformation(
                    regToUser = lambda x : float((x - 2048)) * 40.95994
                    ,userToReg = lambda x : (x * 40.95994) + 2048)))

addReg(RegisterEditor(0x4,"Vb"
                ,defaultValue = 0
                ,regRange = zeroTo(0xFFF)
                ,name = "Vs_under"
                ,description = "under-voltage protection threshold (V)"
                ,transformation = Transformation(
                    regToUser=lambda x: float(x/128.189)
                    ,userToReg=lambda x: (x *128*189))))

addReg(RegisterEditor(0x6,"Vs"
                ,defaultValue = 2047
                ,regRange = zeroTo(0xFFF)
                ,name = "Vs_over"
                ,description = "over-voltage protection threshold (V)"
                ,transformation = Transformation(
                    regToUser=lambda x: float(x/128.189)
                    ,userToReg=lambda x: (x *128*189))))

addReg(RegisterEditor(0x24,"Te"
                ,defaultValue = 1000
                ,regRange = zeroTo(100000000)
                ,name = "t_error"
                ,description = "time before error detection (us)"
                ,transformation = Transformation(
                    regToUser=lambda x: float(x/100000)
                    ,userToReg=lambda x: (x *100000))))

addReg(RegisterEditor(0x51,"Ms"
                ,defaultValue = 0
                ,regRange = zeroTo(8)
                ,name = "DISPLAYS: \n scope_mode"
                ,description = "VGA_scope presets(0-8)"))

addReg(RegisterEditor(0x14,"St"
                ,defaultValue = 0
                ,regRange = between(-2048, 2048)
                ,name = "scp_thresh"
                ,description = "Threshold for VGA-oscilloscope"))

addReg(RegisterEditor(0xEF,"D"
                ,defaultValue = 11
                ,regRange = zeroTo(15)
                ,name = "disp_set"
                ,description = "data switch for 7-segment display"))

for reg in registers.values():
    frame = Frame(user_interface)
    reg.draw(frame)
    frame.pack()

class DisplayCompositor:
    def __init__(self, parent
            ,identification
            ,column
            ,formatType="{0}"
            ,transformations=[]
            ,side=LEFT
            ,fill=X
            ,**kwarfs):
        self.identification = identification
        self.column = column
        self.formatType = formatType
        self.transformations = transformations
        self.var = StringVar()
        self.frame = Frame(parent)
        self.labelId = Label(self.frame, text=identification)
        self.labelId.pack(side=LEFT)
        self.labelData= Label(self.frame, textvariable=self.var)
        self.labelData.pack(side=LEFT)
        self.frame.pack(side=side, fill=X, padx=80)

    def draw(self, data):
        """
        Fill the display with latest available value.
        """
        self.var.set(self.formatType.format(self.transformations(data[-1, self.column])))

    def getDisId(self):
        return self.identification

    @staticmethod
    def addDisplay(displays, newDisplay):
        if newDisplay.getDisId() in displays.keys():
            raise Exception("Double definition of display") 
        else:
            displays[newDisplay.getDisId()] = newDisplay
            logging.debug("added display")
        return newDisplay

displays = {}
DisplayCompositor.addDisplay(displays, DisplayCompositor(bottom_displays
                            ,"MOSFETS temperature: "
                            ,4
                            ,formatType="{0:.1f} [degrees Celcius]"
                            ,transformations=lambda x:float(x-1940)/3.853
                            ))

DisplayCompositor.addDisplay(displays, DisplayCompositor(bottom_displays
                            ,"Errors: "
                            ,14
                            ,formatType="{0:b}"
                            ,transformations=lambda x:int(x)
                            ))

class FigureCompositor:
    def __init__(self, parent
            ,identification
            ,columns
            ,ylabel = [""]
            ,transformations=[]
            ,cross=False
            ,legend=False
            ,figsize=(9,3)
            ,dpi=100
            ,side=LEFT
            ,fill=BOTH
            ,**kwargs):
        self.identification = identification
        self.transformations = transformations
        if isinstance(columns, list) and isinstance(transformations, list):
            self.columns = columns
            if len(transformations) == 0:
                for item in range(len(columns)):
                    self.transformations.append(lambda x : x)
        self.figure = plt.Figure(figsize=figsize, dpi=dpi)
        self.ax = self.figure.add_subplot(111)
        self.ylabel=ylabel
        self.legend = legend
        self.cross = cross

        self.filter = None
        self.ylimits = None
        if kwargs is not None:
            for key, value in kwargs.items():
                if key == 'filters':
                    self.filter = value
                if key == 'ylimits':
                    if isinstance(value, tuple) and len(value) == 2:
                        self.ylimits = value

        self.canvas = FigureCanvasTkAgg(self.figure, parent)
        self.canvas.get_tk_widget().pack(side=side, fill=fill)
        #self.canvas.draw()

    def draw(self, data):
        """
        Fill the figure with data.
        """
        self.ax.clear()
        x_items = list(range(0, data.shape[0]))

        #Apply transformations and filtering
        dummy = []
        for counter, column in enumerate(self.columns):
            dummy.append(list(map(self.transformations[counter], data[:, column])))
            if self.filter is not None:
                if isinstance(self.filter, list):
                    try:
                        self.filter[counter]
                    except IndexError:
                        continue
                    dummy[counter] = self.filter[counter].butter_lowpass_filter(dummy[counter])

        else:
            if self.cross:
                #FIXME: assumes just 2 columns
                dummy.append([item[0]*item[1] for item in zip(dummy[0], dummy[1])])

        for index in range(len(dummy)):
            self.ax.plot(x_items, dummy[index])
        else:
            if self.legend:
                self.ax.legend(self.ylabel)
            self.ax.grid()
            if self.ylimits is not None:
                self.ax.set_ylim([self.ylimits[0], self.ylimits[1]])
            self.ax.set_title(self.identification)
            self.canvas.draw()

    def getFigId(self):
        return self.identification

    @staticmethod
    def addFigure(figures, newFigure):
        if newFigure.getFigId() in figures.keys():
            raise Exception("Double definition of figure") 
        else:
            figures[newFigure.getFigId()] = newFigure
        return newFigure


figures = {}
FigureCompositor.addFigure(figures, FigureCompositor(upper_visuals
                           ,"current/voltage/power"
                           ,[1,0]
                           ,transformations=[lambda x: float(x - 2048)/40.95, lambda x: float(x/128.189)]
                           ,ylabel=["current [A]", "voltage [V]", "power [W]"]
                           ,legend=True
                           ,cross=True
                           ,filters=[Filter(3,150)]
                           ))

FigureCompositor.addFigure(figures, FigureCompositor(upper_visuals
                           ,"thrust"
                           ,[2]
                           ,ylabel=["Thrust [g]"]
                           ,filters=[Filter(10,150)]
                           ,ylimits=(0,1500)
                           ,legend=True
                           ))

FigureCompositor.addFigure(figures, FigureCompositor(lower_visuals
                          ,"current"
                           ,[1,1]
                           ,transformations=[lambda x: float(x - 2048)/40.95,lambda x: float(x - 2048)/40.95]
                           ,ylabel=["filtered current [A]", "raw current[A]"]
                           ,legend=True
                           ,filters=[Filter(3, 150)]
                           ,ylimits=(-1,1)
                           ))

FigureCompositor.addFigure(figures, FigureCompositor(lower_visuals
                           ,"rpm"
                           ,[3]
                           ,ylabel=["rpm [1/min]"]
                           ,legend=True
                           ,ylimits=(0, 30000)
                           ,))

def visualsUpdateCallback(*args):
    """
    Uses 2 globals: figures map and threadMessage instance
    """
    for key, value in figures.items():
        value.draw(threadMessage.readBuffer())
    for key, value in displays.items():
        value.draw(threadMessage.readBuffer())

root.bind("<<GeneratePlots>>", visualsUpdateCallback)

def restoreDefaults():
    serialCommander.writeCommand("R\n")

def resetSystem():
    serialCommander.writeCommand("X\n")

def standbySystem():
    serialCommander.writeCommand("Y\n")

def armSystem():
    serialCommander.writeCommand("Z\n")

Button(user_interface,text = "restore defaults",command = restoreDefaults).pack(side=BOTTOM)
Button(user_interface,text = "reset",command = resetSystem).pack(side=BOTTOM)
Button(user_interface,text = "standby",command = standbySystem).pack(side=BOTTOM)
Button(user_interface,text = "arm",command = armSystem).pack(side=BOTTOM)

content_text.pack(expand='yes', fill='both')
scroll_bar = Scrollbar(content_text)
content_text.configure(yscrollcommand=scroll_bar.set)
scroll_bar.config(command=content_text.yview)
scroll_bar.pack(side='right', fill='y')

if __name__ == '__main__':
    serialThread = Thread(target=SerialCommandConsumer(), name='serialCommander', args=(threadMessage,))
    serialThread.start()
    root.mainloop()
    threadMessage.halt_thread = True
    serialThread.join()
