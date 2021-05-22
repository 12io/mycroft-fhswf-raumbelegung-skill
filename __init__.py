import re
import requests
import xml.etree.ElementTree as ET
from datetime import date
from adapt.intent import IntentBuilder
from mycroft import MycroftSkill, intent_handler

locationMap = {'Is': 'Iserlohn', 'Ha': 'Hagen', 'Ls': 'Lüdenscheid', 'Me': 'Meschede', 'So': 'Soest', 'Z': 'Hagen IAH'}
def getVPISActivities(location=None, semester=None, day=None):
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
    
    if semester: finalUrl = re.sub('[WS]S[0-9]{4}', semester, finalUrl) 
    if day: finalUrl += "&Tag=" + str(date.today())

    return requests.get(finalUrl).content

def parseVpisXml(xml, fromFile=0):
    vpisResponseXML = ET.parse(xml).getroot() if fromFile == 1 else ET.fromstring(xml)
    
    # Die Raumbelegung für den gesamten Standort X
    raumbelegung = {} # für die Suche nach einem Raum

    # für jedes <activity>-Element innerhalb des <activities>-Element im XML-Pfad
    # oder auch: für jede veranstaltungs...
    for activityXML in vpisResponseXML.findall('./activities/activity'):
        # ... den Namen, die Art, Tagen an denen Sie stattfinden sowie Räume in denen sie stattfinden zwischenspeichern
        veranstaltungsname=activityXML.find('./name').text
        veranstaltungsart=activityXML.find('./activity-type').text
        veranstaltungstage=activityXML.findall('./activity-dates/activity-date')
        veranstaltungsraeume=activityXML.findall('./activity-locations/activity-location')

        # für jeden Raum 
        for raum in veranstaltungsraeume:
            raumnummer = raum.text
            for tag in veranstaltungstage:
                veranstaltungsdatum = tag.get('date')
                veranstaltungsbeginn = tag.get('begin')
                veranstaltungsende = tag.get('end')
                veranstaltung = {'name': veranstaltungsname, 'typ': veranstaltungsart, 'ende': veranstaltungsende}
                if raumnummer not in raumbelegung:
                    raumbelegung[raumnummer] = {}
                if veranstaltungsdatum not in raumbelegung[raumnummer]:
                    raumbelegung[raumnummer][veranstaltungsdatum] = {}
                if veranstaltungsbeginn not in raumbelegung[raumnummer][veranstaltungsdatum]:
                    raumbelegung[raumnummer][veranstaltungsdatum][veranstaltungsbeginn] = veranstaltung
        return raumbelegung

class FhRoomOccupancySkill(MycroftSkill):
    def __init__(self):
        super(FhRoomOccupancySkill, self).__init__(name="FhRoomOccupancySkill")
    
    def __initialize__(self):
        self.speak("Hallo, ich bin der FhRoomOccupancySkill, oder auch zu Deutsch: FhRaumbelegungsSkill")

def create_skill():
    return FhRoomOccupancySkill()