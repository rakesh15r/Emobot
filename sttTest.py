import pyttsx3
engine = pyttsx3.init() # object creation

# RATE
rate = engine.getProperty('rate')   # getting details of current speaking rate
print (rate)                        # printing current voice rate
# engine.say('My current speaking rate is ' + str(rate))
# engine.runAndWait()
engine.setProperty('rate', 125)
rate = engine.getProperty('rate')   # getting details of current speaking rate
# print (rate)   
engine.say('My current speaking rate is ' + str(rate))
engine.runAndWait()