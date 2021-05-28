import re
import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from datetime import date
from multi_key_dict import multi_key_dict
from mycroft import MycroftSkill, intent_handler
from os import listdir, mkdir
from os.path import join

VPIS_BASE_URL = 'https://vpis.fh-swf.de'
VPIS_CONTROL_URL = VPIS_BASE_URL + '/vpisapp.php'
# location = path after base url ;SEMESTER; is used here as a variable.
VPIS_COURSES_URL_LOCATION = '/;SEMESTER;/faecherangebotplanung.php3'

fhswfLocationMap = multi_key_dict()
fhswfLocationMap['iserlohn', 'is', 'frauenstuhlweg','frauenstuhl weg', 'campus iserlohn'] = 'Iserlohn'
fhswfLocationMap['hagen', 'ha', 'haldener strasse', 'haldener straße', 'haldener str', 'campus hagen'] = 'Hagen'
fhswfLocationMap['lüdenscheid', 'luedenscheid', 'ls', 'bahnhofsallee', 'campus luedenscheid', 'campus lüdenscheid'] = 'Lüdenscheid'
fhswfLocationMap['meschede', 'me', 'lindenstrasse','lindenstraße','linden straße','linden strasse','linden str', 'campus meschede'] = 'Meschede'
fhswfLocationMap['soest', 'so', 'lübecker ring', 'luebecker ring', 'campus soest'] = 'Soest'
# location "Im Alten Holz" seems to be invalid for API
# fhswfLocationMap['im alten holz', 'hagen iah', 'ha iah', 'hagen im alten holz'] = 'Hagen IAH'

fhswfLocationVpisShortKey = {'Iserlohn': 'Is', 'Hagen': 'Ha', 'Lüdenscheid': 'Ls', 'Meschede': 'Me', 'Soest': 'So' } #, 'Hagen IAH': 'Z'}

def normalizeCourseString(string):
    string = re.sub(r'[\(\)\:,]', r'', string)
    string = re.sub(r'([\s]+\- )', r'', string)
    string = re.sub(r'[/&]', r' und ', string)
    string = re.sub(r'[\s]+', r' ', string)
    return string.lower()

def getVPISActivities(location, semester = None, day = None):
    """Queries VPIS for ooccupied rooms.

    Parameters
    ----------
    location: string
        Required. Should contain a location which is mapped to a short string within locationMap-Array.
        VPIS API has no implementation for inter-site queries for multiple locations.
    
    semester: string, default = None
        Optional. VPIS API always uses current semester. But if given we use it here
        to request the right semester url for data.

    day: string, default = None
        Optional. VPIS API always uses current day. But if given, we append it to the request url
        to get the data for a specific day.
    
    Returns
    -------
    occupiedRooms: { <roomNumber>: { <day>: { <time>: { <activityName>: }{}}}}}
        Nested dict containing all activites for the queried day with roomNumber as keys to query for specific activities by roomNumber.
        
    courses: { <courseName>: { <day>: { <roomNumber>: {<time>: {}}}}}
        Nested dict containing all activities for the queried day with courseName as keys to query for specific activity by courseName.
    
    file: string
    Notes
    -----
    An example of the returned data structures:
    
    occupiedRooms = { 'Is-H409': { '2021-04-12': { '09:45': { 'Programmierung mit C++2': { 'type': 'Praktikum', 'ende': '11:15' },
                                                   '08:00': { 'Programmierung mit C++2': { 'type': 'Praktikum', 'ende': '09:30' },
                                                   '12:00': { 'Programmierung mit C++2': { 'type': 'Praktikum', 'ende': '13:30' }
                                   },
                                   '2021-04-19': { '09:45': { 'Programmierung mit C++2': { 'type': 'Praktikum', 'ende': '11:15' },
                                                   '08:00': { 'Programmierung mit C++2': { 'type': 'Praktikum', 'ende': '09:30' },
                                                   '12:00': { 'Programmierung mit C++2': { 'type': 'Praktikum', 'ende': '13:30' }
                                   }
                      },
                      'Is-ZE04': { ... }
    }
    
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
    }    
    """
    
    if not location in fhswfLocationMap:
        raise AttributeError('Invalid parameter: location')

    vpisControlResponse = requests.get(VPIS_CONTROL_URL)
        
    if not vpisControlResponse.status_code == 200:
        raise RuntimeError('Could not connect to VPIS: HTTP status code ' + str(vpisControlResponse.status_code))
    
    elif not re.search('application/xml', vpisControlResponse.headers['content-type']):
        raise RuntimeError('Response is no valid XML.')

    vpisControlXml = vpisControlResponse.content
    
    locationsXml = ET.fromstring(vpisControlXml)
    for locationChild in locationsXml.findall('./locations'):
        if locationChild.text == fhswfLocationMap[location]:
            url=locationChild.get('href')
            break
    
    finalUrl = requests.get(url).url
    
    if semester:
        finalUrl = re.sub('[WS]S[0-9]{4}', semester, finalUrl)
    
    if day:
        finalUrl += '&Tag=' + day

    vpisResponse = requests.get(finalUrl)
    if not vpisResponse.status_code == 200:
        raise RuntimeError('Could not connect to VPIS: HTTP status code ' + str(vpisResponse.status_code))
    elif not re.search('application/xml', vpisResponse.headers['content-type']):
        raise RuntimeError('Response is no valid XML.')

    vpisResponseXml = ET.fromstring(vpisResponse.content)
    occupiedRooms = {}
    courses = {}

    # for each <activity> element within <activities> element inside XML
    # "for each course..."
    for activityXML in vpisResponseXml.findall('./activities/activity'):
        # ... save name, type, all dates(!) for this semester, all rooms(!) for this semester
        courseName=normalizeCourseString(activityXML.find('./name').text)
        courseType=activityXML.find('./activity-type').text
        courseDates=activityXML.findall('./activity-dates/activity-date')
        courseRooms=activityXML.findall('./activity-locations/activity-location')

        # for each room (because at the end of the day, a room can have multiple dates and a date can have multiple times for a course)
        for room in courseRooms:
            roomNumber = room.text
            roomNumberWithoutLocationPrefix = re.findall(r'(?:[A-Za-z]{2}-)(.*)', roomNumber)[0]
            roomNumber = roomNumberWithoutLocationPrefix.lower()
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
        
    return occupiedRooms, courses

def getRoomsByLocation(url = VPIS_CONTROL_URL):
    vpisControlResponse = requests.get(url)
    if not vpisControlResponse.status_code == 200:
        raise RuntimeError("Connect to " + url + " failed. HTTP response code: " + vpisControlResponse.status_code)
    elif not re.search('application/xml', vpisControlResponse.headers['content-type']):
        raise RuntimeError('Response is no valid XML.')
    
    controlXml = ET.fromstring(vpisControlResponse.content)
 
    roomNumbersByLocation = {}
    for locationChild in controlXml.findall('./locations'):
        # for fhswfLocation in fhswfLocationVpisShortKey.keys():
        if locationChild.text not in fhswfLocationMap.values():
            continue
        vpisLocationResponse = requests.get(locationChild.get('href'))
        if not vpisLocationResponse.status_code == 200:
            raise RuntimeError("Could not fetch rooms for {}. HTTP response code: {}".format(locationChild.text, vpisLocationResponse.status_code))
        elif not re.search('application/xml', vpisLocationResponse.headers['content-type']):
            raise RuntimeError('Response is no valid XML.')
        
        locationsXml = ET.fromstring(vpisLocationResponse.content)
        for location in locationsXml.findall('./locations/location'):
            locationName = str(locationChild.text)
            room = str(location.find('./name').text)
            roomWithoutLocationPrefix = re.findall(r'(?:[A-Za-z]{2}-)(.*)', room)[0]
            room = roomWithoutLocationPrefix.lower()

            if locationName not in roomNumbersByLocation:
                roomNumbersByLocation[locationName] = []
            if room not in roomNumbersByLocation[locationName]:
                roomNumbersByLocation[locationName].append(room)
    return roomNumbersByLocation

def getCoursesByLocation():
    overallCoursesByLocation = {}
    today = date.today()
    
    for locationKey in fhswfLocationVpisShortKey.values():
        urlLocations = [ re.sub(';SEMESTER;', 'SS' + str(today.year), VPIS_COURSES_URL_LOCATION), re.sub(';SEMESTER;', 'WS' + str(today.year), VPIS_COURSES_URL_LOCATION) ]
        
        for urlLocation in urlLocations:
            url = VPIS_BASE_URL + urlLocation
            site = requests.get(url, params = {'Fachbereich': locationKey, 'sort': 'fachname', 'Template': 'None'})
            if not site.status_code == 200:
                continue
            
            if not locationKey in overallCoursesByLocation:
                overallCoursesByLocation[locationKey] = []
            site = BeautifulSoup(site.text)
            courseTags = site.findAll("span", {"style": "white-space:nowrap;"})
            
            for courseTag in courseTags:
                courseName = normalizeCourseString(str(courseTag.text))
                overallCoursesByLocation[locationKey].append(courseName)
    
    # remove possible (equally written) duplicates:
    for a in overallCoursesByLocation:
        overallCoursesByLocation[a] = list(dict.fromkeys(overallCoursesByLocation[a]))
    
    return overallCoursesByLocation

class FhRoomOccupancySkill(MycroftSkill):
    def __init__(self):
        super(FhRoomOccupancySkill, self).__init__(name="FhRoomOccupancySkill")
    
    def initialize(self):
        self.register_entity_file('location.entity')
        self.register_entity_file('day.entity')

        # We need to build our room.entity and course.entity "dynamically" here (fetching from vpis)
        # and register afterwards
        
        # fetch rooms and build room.entity #
        self.roomsByLocation = getRoomsByLocation()
        if not self.roomsByLocation:
             self.log.error('No room entities. Skill may not function properly!')
        else:
            self.log.info('Generating room.entity for every locale')
            for localeDir in listdir(join(self.root_dir, 'locale')):
                roomEntityFile = open(join(self.root_dir, 'locale', localeDir, 'room.entity'), 'w')
                for rooms in self.roomsByLocation.values():
                    if not rooms:
                        continue
                    for roomNr in rooms:
                        roomEntityFile.writelines(roomNr + '\n')
                roomEntityFile.close()
            self.register_entity_file('room.entity')
        # end of room.entity building #

        # fetch courses and build course.entity #
        self.coursesByLocation = getCoursesByLocation()
        if not self.coursesByLocation:
            self.log.error('No course entities. Skill may not function properly!')
        else:
            print('Generating course.entity for every locale')
            for localeDir in listdir(join(self.root_dir, 'locale')):
                    entityFile = open(join(self.root_dir, 'locale', localeDir, 'course.entity'), 'w')
                    for courses in self.coursesByLocation.values():
                        if not courses:
                            continue
                        for course in courses:
                            entityFile.writelines(course.lower() + '\n')
                    entityFile.close()
            self.register_entity_file('course.entity')
        # end of course.entity building #

        self.log.info('FhRoomOccupancySkill initialized.')

    # intents for information about how to use this skill
    @intent_handler('tell.me.about.this.skill.intent')
    def tellMeAboutThisSkill(self, message):
        self.log.info(message.serialize())
        self.speak_dialog('you.can.ask.me.about.rooms.and.courses')
        
    @intent_handler('how.do.i.query.for.a.room.intent')
    def handleHowDoIqueryForAroom(self, message):
        self.log.info(message.serialize())
        self.speak_dialog('for.example.you.can.ask.me')
        self.speak_dialog('this.is.how.you.query.for.a.room')
    
    @intent_handler('how.do.i.query.for.a.course.intent')
    def handleHowDoIqueryAroom(self, message):
        self.log.info(message.serialize())
        self.speak_dialog('for.example.you.can.ask.me')
        self.speak_dialog('this.is.how.you.query.for.a.course')

    # actual action intents #

    # query for a room
    @intent_handler('what.does.take.place.in.room.x.intent')
    def handleWhatDoesTakePlaceIn(self, message):
        self.log.info(message.serialize())
        roomEntity = message.data.get('room')
        locationEntity = message.data.get('location')
        dayEntity = message.data.get('day')

        if not locationEntity or locationEntity not in fhswfLocationMap:
            self.log.info("Asking for another location")
            locationEntity = self.get_response('please.tell.me.where.to.look.for.x', {'queryString': roomEntity})
            self.log.info("New location:{}".format(locationEntity))
        
        if not dayEntity:
            dayEntity = str(date.today().isoformat())
            self.log.info("Set date to todays date:{}".format(dayEntity))
        
        try:    
            occupiedRooms, courses = getVPISActivities(locationEntity)
        except AttributeError as err:
            self.speak_dialog('invalid.location', {'location': locationEntity})
            return 1

        if not occupiedRooms:
            self.log.info("Query Failed line 280")
            self.speak_dialog('room.not.found', {'room': roomEntity})
            return 1
        elif not courses:
            self.log.info("Query Failed line 284")
            self.speak_dialog('course.not.found')
            return 1
        self.log.info("\"{}\" remove spaces ===> \"{}\"".format(roomEntity, roomEntity.replace(' ', '')))
        roomEntity = roomEntity.replace(' ', '')
        self.log.info(roomEntity)

        if roomEntity in occupiedRooms:
            self.speak_dialog('following.courses.take.place.in.room.x', {'room': roomEntity})
            for courseTimeBegin in occupiedRooms[roomEntity][dayEntity]:
                for courseName in occupiedRooms[roomEntity][dayEntity][courseTimeBegin]:
                    self.speak_dialog('course.x.takes.place.in.room.y', {'time':courseTimeBegin, 'course': courseName, 'courseType': occupiedRooms[roomEntity][dayEntity][courseTimeBegin]['type'], 'courseEndTime':occupiedRooms[roomEntity][dayEntity][courseTimeBegin]['end']})
        else:
            self.log.info("Query Failed line 299")
            self.speak_dialog('room.not.found', {'room': roomEntity})
        
        return 0

    # query for a course
    @intent_handler('where.does.course.x.take.place.intent')
    def handleWhereDoesCourseTakePlace(self, message):
        self.log.info(message.serialize())
        courseEntity = message.data.get('course')
        locationEntity = message.data.get('location')
        dayEntity = message.data.get('day')
        
        if not locationEntity or locationEntity not in fhswfLocationMap:
            self.log.info("Asking for another location")
            locationEntity = self.get_response('please.tell.me.where.to.look.for.x', {'queryString': courseEntity})
            self.log.info("New location:{}".format(locationEntity))

        if not dayEntity:
            dayEntity = str(date.today().isoformat())
            self.log.info("Set date to todays date:{}".format(dayEntity))

        try:    
            occupiedRooms, courses = getVPISActivities(locationEntity)
        except AttributeError as err:
            self.speak_dialog('invalid.location', {'location': locationEntity})
            return 1

        if not occupiedRooms and not courses:
            self.log.info("Query Failed line 367")
            self.speak_dialog('no.courses.for.location.x', {'course': courseEntity, 'location': locationEntity})
            return 1
        
        self.log.info('normalizeCourseString("{}")'.format(courseEntity))
        courseEntity = normalizeCourseString(courseEntity)
        self.log.info(courseEntity)
        
        if courseEntity in courses:
            if dayEntity in courses[courseEntity]:
                for room in courses[courseEntity][dayEntity]:
                    self.log.info({'room': room, 'location': locationEntity, 'course': courseEntity})
                    self.speak_dialog('course.x.takes.place.in.following.rooms', {'room': room, 'location': locationEntity})
                    for time in courses[courseEntity][dayEntity][room]:
                        self.log.info({'time': time, 'courseType': courses[courseEntity][dayEntity][room][time]['type'], 'courseEndTime': courses[courseEntity][dayEntity][room][time]['end']})
                        self.speak_dialog('course.x.takes.place.in.room.y', {'time': time, 'course': courseEntity, 'courseType': courses[courseEntity][dayEntity][room][time]['type'], 'courseEndTime': courses[courseEntity][dayEntity][room][time]['end']})
        else:
            self.log.info("Query Failed line 383")
            self.speak_dialog('no.courses.for.location.x', {'course': courseEntity, 'location': locationEntity})
        
        return 0

        def stop(self):
            pass
        
def create_skill():
    return FhRoomOccupancySkill()