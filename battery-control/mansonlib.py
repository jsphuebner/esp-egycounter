
'''

1.Ubuntu System 

install python3:

sudo apt-get install python3

install serial :

sudo apt-get install python3-serial



2.Fedora System

install python3

yum install python3

install serial:

curl -O https://bootstrap.pypa.io/get-pip.py

sudo python3 get-pip.py

'''

#!/usr/bin/python
import time, serial,sys
import string
import re
import operator

class InstrumentException(Exception): pass

#print sys.getdefaultencoding() 

class InstrumentInterface:
	def __init__(self):
		self.sp = None
	def Init(self,com_port,*baudrate):

		baud_tuple = baudrate[0]
		if  baud_tuple:
			baud = int(list(baud_tuple)[0])
		try:
			if not baud_tuple:
				self.sp = serial.Serial(com_port,baudrate=9600,bytesize=8,parity='N',stopbits=1,timeout=0.1)
				self.sp.flushInput() 
				self.sp.flushOutput() 
			else :
				self.sp = serial.Serial(com_port,baudrate=baud,bytesize=8,parity='N',stopbits=1,timeout=0.1)
				self.sp.flushInput()
				self.sp.flushOutput() 
		except Exception:
			self.sp = None
		if self.sp == None:
			return False
		return True
		
	def Close(self):
		if type(self.sp) != type(None):
			self.sp.close()
			self.sp = None
			return True
		return False
		
	def GetInf(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write('GMOD\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('GMOD\r')
				response = self.sp.readline()
			if response == '':
				return "DeviceOff"
			pattern = re.compile('.*\d{4}\s')
			match = pattern.match(response)
			if match:
				if operator.eq("HCS-",response[0:4]) == 0:
					return "HCS-" + match.group()
				return match.group()
			return "DeviceOff"
		return "DeviceOff"
	def OutOn(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write('SOUT1\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('SOUT1\r')
				response = self.sp.readline()
			if  response != '':
				return response
			else:
				return False
		return False
	def OutOff(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write('SOUT0\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('SOUT0\r')
				response = self.sp.readline()
			if  response != '':
				return response
			else:
				return False
		return False
	def GetOutPutRead(self,option):
		if type(self.sp) != type(None):
			if isinstance(option,str):
				if option == 'A':
					self.sp.write("GETD\r".encode('ascii'))
					response = self.sp.readline().decode('ascii')
					if response != '':
						volt = int(response[0:4])/float(100)
						curr = int(response[4:8])/float(100)
						if response[8:9] == '0':
							mode = "CV"
						elif response[8:9] == '1':
							mode = "CC"
						else: 
							return False
						return str(volt) + " " + str(curr) + " " + mode
					else:
						return False
			
				elif option == 'V':
					self.sp.write("GETD\r".encode('ascii'))
					response = self.sp.readline().decode('ascii')
					if response != '':
						volt = int(response[0:4])/float(100)
						return volt
					else:
						return False
				elif option == 'C':
					self.sp.write("GETD\r".encode('ascii'))
					response = self.sp.readline().decode('ascii')
					if response != '':
						curr = int(response[4:8])/float(100)
						return curr
					return False
				elif option == 'S':
					self.sp.write("GETD\r".encode('ascii'))
					response = self.sp.readline().decode('ascii')
					if response != '':
						if response[8:9] == '0':
							self.sp.read(4)
							return "CV"
						elif response[8:9] == '1':
							return "CC"
						else: 
							return False		
				return False
			return False
		return False
	def SetVolt(self,volt):
		if type(self.sp) != type(None):
			if isinstance(volt,(int,float)):
				if 0 < volt and volt < 1:
					volt = int(volt * 10)
					cmd = "VOLT" + "00"+ str(volt) + "\r"
				elif 1 <= volt and volt < 10:
					volt = int(volt * 10)
					cmd = "VOLT" + "0"+ str(volt) + "\r"
				elif 10 <= volt and volt < 99:
					volt = int(volt * 10)
					cmd = "VOLT" + str(volt) + "\r"	
				else :
					return False
				if sys.version > '3':
					self.sp.write(cmd.encode('ascii'))
					response = self.sp.readline().decode('ascii')
				else:
					self.sp.write(cmd)
					response = self.sp.readline()
				if response == '':
					return False
				return response
			return False
		return False
	def SetCurr(self,curr):
		model_list = ['HCS-3102','HCS-3014','HCS-3204']
		if type(self.sp) != type(None):
			if isinstance(curr,(int,float)):
				model = self.GetInf()
				model_mark = 0
				for x in range(len(model_list)):
					if operator.eq(model[0:8],model_list[x]) == 1:
						if 0 <= curr and curr <= 0.09:
							curr = int(curr * 100)
							cmd = "CURR" + "00"+ str(curr) + "\r"
						elif 0.1 <= curr and curr <= 0.99:
							curr = int(curr * 100)
							cmd = "CURR" + "0"+ str(curr) + "\r"
						elif 1 <= curr and curr <= 9.99:
							curr = int(curr * 100)
							cmd = "CURR" + str(curr) + "\r"
						else :
							return False
						model_mark = 1
						break
				if model_mark == 0:				
					if 0 <= curr and curr <= 0.9:
						curr = int(curr * 10)
						cmd = "CURR" + "00"+ str(curr) + "\r"
					elif 1 <= curr and curr < 9.9:
						curr = int(curr * 10)
						cmd = "CURR" + "0"+ str(curr) + "\r"
					elif 10 <= curr and curr <= 99.9:
						curr = int(curr * 10)
						cmd = "CURR" + str(curr) + "\r"	
					else :
						return False
				if sys.version > '3':
					self.sp.write(cmd.encode('ascii'))
					response = self.sp.readline().decode('ascii')
				else:
					self.sp.write(cmd)
					response = self.sp.readline()
				if response == '':
					return False
				return response
			return False
		return False
	def GMax(self,option):
		if type(self.sp) != type(None):
			model_list = ['HCS-3102','HCS-3014','HCS-3204']
			if sys.version > '3':
				self.sp.write("GMAX\r".encode('ascii'))
				response = self.sp.readline().decode('ascii')	
			else:
				self.sp.write('GMAX\r')
				response = self.sp.readline()
			if response == '':
				return False
			maxv = int(response[0:3])
			maxc = int(response[3:6])
			if isinstance(option,str):
				if option == 'V':
					if maxv >= 0 and maxv <= 999 :
						maxv = maxv/float(10)
						return maxv
					else:
						return False
				elif option == 'C':
					model = self.GetInf()
					for x in range(len(model_list)):
						if operator.eq(model[0:8],model_list[x]) == 1:
							maxc = maxc /float(100)
							return maxc
					return maxc/float(10)
				elif option == 'A':
					if maxv >= 0 and maxv <= 999 :
						maxv = maxv/float(10)
					model = self.GetInf()
					for x in range(len(model_list)):
						if operator.eq(model[0:8],model_list[x]) == 1:
							maxc = maxc /float(100)
							return str(maxv) + " " + str(maxc)
					return str(maxv) + " " + str(maxc/float(10))
				return False
			return False
		return False
	def GetSetting(self,option):
		if type(self.sp) != type(None):
			model_list = ['HCS-3102','HCS-3014','HCS-3204']
			if sys.version > '3':
				self.sp.write('GETS\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('GETS\r')
				response = self.sp.readline()
			if response == '':
				return False
			response = re.sub("\D", "", response)
			vseting = int(response[0:3])/float(10)
			csting = int(response[3:6])
			if isinstance(option,str):
				if option == 'V':
					return vseting
				elif option == 'C':
					model = self.GetInf()
					for x in range(len(model_list)):	
						if operator.eq(model[0:8],model_list[x]) == 1:
							csting = csting /float(100)
							return csting
					return csting/float(10)
				elif option == 'A':
					model = self.GetInf()
					for x in range(len(model_list)):
						if operator.eq(model[0:8],model_list[x]) == 1:
							csting = csting /float(100)
							return str(vseting) + " " + str(csting)
					return str(vseting) + " " + str(csting/float(10))
				return False
			return False
		return False
	def RMode(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write('SESS\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('SESS\r')
				response = self.sp.readline()
			if  response != '':
				return response
			else:
				return False
		return False
	def Pset(self,num,volt,curr):
		if type(self.sp) != type(None):
			num_max = 3
			if isinstance(num,int):
				if num > num_max-1 or num < 0:
					return False
				for x in range(num_max):
					if x == num :
						index = num + x
						break
			model_list = ['HCS-3102','HCS-3014','HCS-3204']
			list_v = ['0','3','7','10','14','17']
			list_c = ['3','6','10','13','17','20']
			if sys.version > '3':
				self.sp.write('GETM\r'.encode('ascii'))
				time.sleep(0.5)
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('GETM\r')
				time.sleep(0.5)
				response = self.sp.readline()
			if response == '' :
				return False
			response = list(response)
			if isinstance(volt,(int,float)):
				if 0 <= volt and volt < 1:
					volt = int(volt * 10)
					response[(int(list_v[index])):(int(list_v[index+1]))] = '00' + str(volt)
				elif 1 <= volt and volt < 10:
					volt = int(volt * 10)
					response[(int(list_v[index])):(int(list_v[index+1]))] = '0' + str(volt)
				elif 10 <= volt and volt < 100:
					volt = int(volt * 10)
					response[(int(list_v[index])):(int(list_v[index+1]))] = str(volt)
				else :
					return False
			model = self.GetInf()
			model_mark = 0
			if model == '':
				return False
			if isinstance(curr,(int,float)):
				for x in range(len(model_list)):	
					if operator.eq(model[0:8],model_list[x]) == 1:
						if 0 <= curr and curr < 1:
							curr = int(curr * 100)
							response[(int(list_c[index])):(int(list_c[index+1]))] = '0' + str(curr)
						elif 1 <= curr and curr < 10:
							curr = int(curr * 100)
							response[(int(list_c[index])):(int(list_c[index+1]))] = str(curr)
						else :
							return False
						model_mark = 1
						break
			else :
				return False
			if model_mark == 0 :
				if 0 <= curr and curr < 1:
					curr = int(curr * 10)
					response[(int(list_c[index])):(int(list_c[index+1]))] = '00' + str(curr)
				elif 1 <= curr and curr < 10:
					curr = int(curr * 10)
					response[(int(list_c[index])):(int(list_c[index+1]))] = '0' + str(curr)
				elif 10 <= curr and curr < 99:
					curr = int(curr * 10)
					response[(int(list_c[index])):(int(list_c[index+1]))] = str(curr)
				else :
					return False
			response = ''.join(response)
			response = response[0:6] + response[7:13]+response[14:20]
			cmd = 'PROM' + response + '\r'
			if sys.version > '3':
				self.sp.write(cmd.encode('ascii'))
				time.sleep(0.5)
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write(cmd)
				time.sleep(0.5)
				response = self.sp.readline()
			if response == '':
				return False
			return response		
		return False
	def GPset(self,index,option):
		if type(self.sp) != type(None):
			model_list = ['HCS-3102','HCS-3014','HCS-3204']
			model = self.GetInf()
			model_mark = 0
			list_v = ['0','3','6','9','12','15']
			list_c = ['3','6','9','12','15','18']
			max_index = 3
			if isinstance(index,(int,float)):
				if index<0 or index > max_index-1:
					return False
			for x in range(max_index):
				if x == index :
					index = index + x
					break
			if sys.version > '3':
				self.sp.write('GETM\r'.encode('ascii'))
				time.sleep(0.5)
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('GETM\r')
				time.sleep(0.5)
				response = self.sp.readline()
			if response == '' :
				return False
			response = re.sub("\D", "", response)
			if option == 'A':
				volt = int(response[(int(list_v[index])):(int(list_v[index+1]))])/float(10)
				for x in range(len(model_list)):	
					if operator.eq(model[0:8],model_list[x]) == 1:
						curr = int(response[(int(list_c[index])):(int(list_c[index+1]))])/float(100)
						return str(volt) + " " + str(curr)
				curr = int(response[(int(list_c[index])):(int(list_c[index+1]))])/float(10)
				return str(volt) + " " + str(curr)
			elif option == 'V':
				volt = int(response[(int(list_v[index])):(int(list_v[index+1]))])/float(10)
				return volt			
			elif option == 'C':
				for x in range(len(model_list)):	
					if operator.eq(model[0:8],model_list[x]) == 1:
						curr = int(response[(int(list_c[index])):(int(list_c[index+1]))])/float(100)
						return curr
				curr = int(response[(int(list_c[index])):(int(list_c[index+1]))])/float(10)
				return curr	
		return False
	def RPreset(self,index):
		if type(self.sp) != type(None):
			index_max = 3
			if isinstance(index,int):
				if index > index_max-1 or index < 0:
					return False
				cmd = 'RUNM' + str(index) + '\r'
				if sys.version > '3':
					self.sp.write(cmd.encode('ascii'))
					response = self.sp.readline().decode('ascii')
				else:
					self.sp.write(cmd)
					response = self.sp.readline()
				if response == '' :
					return False
				return response
		return False
	def GetOutVolt(self):
		if type(self.sp) != type(None):
			self.sp.write("GETD\r".encode('ascii'))
			response = self.sp.readline().decode('ascii')
			if response != '':
				return int(response[0:4])/float(100)
		return False
	def GetOutCurr(self):
		if type(self.sp) != type(None):
			self.sp.write("GETD\r".encode('ascii'))
			response = self.sp.readline().decode('ascii')
			if response != '':
				return int(response[4:8])/float(100)
		return False
	def GetOutMode(self):
		if type(self.sp) != type(None):
			self.sp.write("GETD\r".encode('ascii'))
			response = self.sp.readline().decode('ascii')
			if response != '':
				if response[8:9] == '0':
					self.sp.read(4)
					return "CV"
				elif response[8:9] == '1':
					return "CC"
		return False
class HCS(InstrumentInterface):
	def OpenPort(self,com_port,*baudrate):
		"Initialize the base class"
		return InstrumentInterface.Init(self,com_port,baudrate)
	def ClosePort(self):
		"Close serial port"
		return self.Close()
	def GetModel(self):
		"Get the HCS model"
		response = self.GetInf()
		return response
	def TimeNow(self):
		"Returns a string containing the current time"
		return time.asctime()	
	def OutputOn(self):
		"Set output on"
		return self.OutOn()		
	def OutputOff(self):
		"Set output off"
		return self.OutOff()		
	def GetOutputReading(self,option):
		"return output code "
		response = self.GetOutPutRead(option)
		return response
	def SetOutputVoltage(self,volt):
		"Sets the output voltage"
		msg = "Set output voltage"
		response = self.SetVolt(volt)
		return response
	def SetOutputCurrent(self,curr):
		"Sets the output current"
		msg = "Set output current"
		response = self.SetCurr(curr)
		return response
	def GetMaxSet(self,option):
		"Get maximun voltage and current"
		return self.GMax(option)
	def GetOutputSetting(self,option):
		"Get the seting voltage and current"
		return self.GetSetting(option)
	def SetRearMode(self):
		"Set Rear mode, disable front buttons"
		return self.RMode()
	def SetPreset(self,num,volt,curr):
		"setting the preset value in HCS"
		return self.Pset(num,volt,curr)
	def GetPreset(self,index,option):
		"get the preset value in HCS"
		return self.GPset(index,option)
	def RunPreset(self,index):
		"run the preset value"
		return self.RPreset(index)
	def GetOutputVoltage(self):
		"get HCS output voltage"
		return self.GetOutVolt()
	def GetOutputCurrent(self):
		"get HCS output current"
		return self.GetOutCurr()
	def GetOutputMode(self):
		"get HCS output mode"
		return self.GetOutMode()

		
#class NTP(InstrumentInterface,HCS):
#	pass
class NTP(InstrumentInterface,HCS):
	def SetOutputVoltage(self,volt):
		if type(self.sp) != type(None):
			if isinstance(volt,(int,float)):
				if 1 <= volt and volt < 10:
					volt = int(volt * 100)
					cmd = "VOLT" + "0" + str(volt) + "\r"
				elif 10 <= volt and volt <= 21:
					volt = int(volt * 100)
					cmd = "VOLT" + str(volt) + "\r"
				else :
					return False
				if sys.version > '3':
					self.sp.write(cmd.encode('ascii'))
					response = self.sp.readline().decode('ascii')
				else:
					self.sp.write(cmd)
					response = self.sp.readline()
				if response == '':
					return False
				return response
			return False
		return False
	def DeleteProtection(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write('SPRO0\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('SPRO0\r')
				response = self.sp.readline()
			if response == '':
				return False
			return True
		return False
	def AddProtection(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write('SPRO1\r'.encode('ascii'))
				response = self.sp.readline().decode('ascii')
			else:
				self.sp.write('SPRO1\r')
				response = self.sp.readline()
			if response == '':
				return False
			return True
		return False
	def SetOutputCurrent(self,curr):
		if type(self.sp) != type(None):	
			if isinstance(curr,(int,float)):
				if 0.25 <= curr and curr < 1:
					curr = int(curr * 1000)
					cmd = "CURR" + "0"+ str(curr) + "\r"
				elif 1 <= curr and curr <= 5.2:
					curr = int(curr * 1000)
					cmd = "CURR" + str(curr) + "\r"	
				else :
					return False
				if sys.version > '3':
					self.sp.write(cmd.encode('ascii'))
					response = self.sp.readline().decode('ascii')
				else:
					self.sp.write(cmd)
					response = self.sp.readline()
				if response == '':
					return False
				return True
			return False
		return False
	def GetOutputVoltage(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write("GETD\r".encode('ascii'))
				response = self.sp.readline().decode('ascii')
				if response != '':
					s = response.split(';')
					return int(s[0])/float(100)
			else :
				elf.sp.write('GETD\r')
				response = self.sp.readline()
				if response != '':
					s = response.split(';')
					return int(s[0])/float(100)
		return False
	def GetOutputCurrent(self):
		if type(self.sp) != type(None):
			if sys.version > '3':
				self.sp.write("GETD\r".encode('ascii'))
				response = self.sp.readline().decode('ascii')
				if response != '':
					s = response.split(';')
					return int(s[1])/float(1000)
			else:
				self.sp.write('GETD\r')
				response = self.sp.readline()
				if response != '':
					s = response.split(';')
					return int(s[1])/float(1000)
		return False
	def GetOutputMode(self):
		if type(self.sp) != type(None):
			self.sp.write("GETD\r".encode('ascii'))
			response = self.sp.readline().decode('ascii')
			if response != '':
				s = response.split(';')
				if s[2] == '0':
					self.sp.read(4)
					return "CV"
				elif s[2] == '1':
					return "CC"
				else :
					return False
		return False
			
if __name__ == '__main__':	
	pass

