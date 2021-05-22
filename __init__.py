import re
import requests
import xml.etree.ElementTree as ET
from datetime import date
from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_handler

locationMap = {'Is': 'Iserlohn', 'Ha': 'Hagen', 'Ls': 'Lüdenscheid', 'Me': 'Meschede', 'So': 'Soest', 'Z': 'Hagen IAH'}
def getVPISActivities(location=None, semester=None, day=None, file=0):
    response=''
    url=''

    if not location:
        raise AttributeError('Missing parameter: location')

    vpisApiXmlResponse = requests.get('https://vpis.fh-swf.de/vpisapp.php')
        
    if not vpisApiXmlResponse.status_code == 200:
        raise RuntimeError('Could not connect to VPIS: HTTP status code ' + str(vpisApiXmlResponse.status_code))
    
    elif not re.search('application/xml', vpisApiXmlResponse.headers['content-type']):
        raise RuntimeError('Response is no valid XML.')
        
    locationsXml = ET.fromstring(vpisApiXmlResponse.content)
    for locationChild in locationsXml.findall('./locations'):
        if locationChild.text == location:
            url=locationChild.get('href')
            break
    
    finalUrl = requests.get(url).url
    
    if semester:
        finalUrl = re.sub('[WS]S[0-9]{4}', semester, finalUrl)
    
    if day:
        finalUrl += '&Tag=' + day

    vpisXml = requests.get(finalUrl).content
    
    if not file == 0:
        with open(file, 'wb') as f:
            f.write(vpisXml)

    return requests.get(finalUrl).content

def parseVpisXml(xml, file=0):
    vpisResponseXML = ET.parse(file).getroot() if not file == 0 else ET.fromstring(xml)
    
    # Example for occupiedRooms structure:
    '''
    occupiedRooms = { 'Is-H409': { '2021-04-12': { '09:45': { 'Programmierung mit C++2': { 'typ': 'Praktikum', 'ende': '11:15' },
                                                   '08:00': { 'Programmierung mit C++2': { 'typ': 'Praktikum', 'ende': '09:30' },
                                                   '12:00': { 'Programmierung mit C++2': { 'typ': 'Praktikum', 'ende': '13:30' }
                                   },
                                   '2021-04-19': { '09:45': { 'Programmierung mit C++2': { 'typ': 'Praktikum', 'ende': '11:15' },
                                                   '08:00': { 'Programmierung mit C++2': { 'typ': 'Praktikum', 'ende': '09:30' },
                                                   '12:00': { 'Programmierung mit C++2': { 'typ': 'Praktikum', 'ende': '13:30' }
                                   }
                      },
                      'Is-ZE04': { ... }
    }
    '''
    occupiedRooms = {}

    # Example for courses structure:
    '''
    courses = 'Programmierung mit C++2': { '2021-04-12': { 'Is-H409': { '09:45': { 'type': 'Praktikum', 'end': '11:15' },
                                                                        '08:00': { 'type': 'Praktikum', 'end': '09:30' },
                                                                        '12:00': { 'type': 'Praktikum', 'end': '13:30' }
                                                         }
                                           },
                                           '2021-04-19': { 'Is-H409': { '09:45': { 'type': 'Praktikum', 'end': '11:15' },
                                                                        '08:00': { 'type': 'Praktikum', 'end': '09:30' },
                                                                        '12:00': { 'type': 'Praktikum', 'end': '13:30' }
                                                         }
                                           },
              'Projekt (Systemintegration)': { ... }
    '''
    courses = {}

    # for each <activity> element within <activities> element inside XML
    # "for each course..."
    for activityXML in vpisResponseXML.findall('./activities/activity'):
        # ... save name, type, all dates(!) for this semester, all rooms(!) for this semester
        courseName=activityXML.find('./name').text
        courseType=activityXML.find('./activity-type').text
        courseDates=activityXML.findall('./activity-dates/activity-date')
        courseRooms=activityXML.findall('./activity-locations/activity-location')

        # for each room (because at the end of the day, a room can have multiple dates and a date can have multiple times for a course)
        for room in courseRooms:
            roomNumber = room.text
            for dateOfDay in courseDates:
                courseDate = dateOfDay.get('date')
                courseTimeBegin = dateOfDay.get('begin')
                courseTimeEnd = dateOfDay.get('end')
                courseDetails = {'type': courseType, 'end': courseTimeEnd}
                
                # fill occupiedRooms:
                if roomNumber not in occupiedRooms:
                    occupiedRooms[roomNumber] = {}
                if courseDate not in occupiedRooms[roomNumber]:
                    occupiedRooms[roomNumber][courseDate] = {}
                if courseTimeBegin not in occupiedRooms[roomNumber][courseDate]:
                    occupiedRooms[roomNumber][courseDate][courseTimeBegin] = {}
                if courseName not in occupiedRooms[roomNumber][courseDate][courseTimeBegin]:
                    occupiedRooms[roomNumber][courseDate][courseTimeBegin][courseName] = courseDetails
                
                # fill courses:
                if courseName not in courses:
                    courses[courseName] = {}
                if courseDate not in courses[courseName]:
                    courses[courseName][courseDate] = {}
                if roomNumber not in courses[courseName][courseDate]:
                    courses[courseName][courseDate][roomNumber] = {}
                if courseTimeBegin not in courses[courseName][courseDate][roomNumber]:
                    courses[courseName][courseDate][roomNumber][courseTimeBegin] = courseDetails
        
    return {'occupiedRooms': occupiedRooms, 'courses': courses}

class FhRoomOccupancySkill(MycroftSkill):
    def __init__(self):
        super(FhRoomOccupancySkill, self).__init__(name="FhRoomOccupancySkill")
    
    def __initialize__(self):
        self.register_entity_file('day.entity')
        self.register_entity_file('location.entity')
        self.log.info('FhRoomOccupancySkill initialized.')

    @intent_handler('fhswf-help.intent')
    def handleFhSwfIntent(self, message):
        self.speak_dialog('fhswf.dialog')

    @intent_handler('what.does.take.place.in.x.intent')
    def handleRoomOccupation(self, message):
        self.log.debug(message)
        

def create_skill():
    return FhRoomOccupancySkill()