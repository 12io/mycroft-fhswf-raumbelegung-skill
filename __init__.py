import requests
import xml.etree.ElementTree as ET
from datetime import date

def getXML(standort=0, semester=0, tag=0):
    if not standort:
        standort = "Is"
    if not semester:
        heute = date.today()
        if 3<= heute.month <=8:
            semester="SS" + str(heute.year)
        else:
            semester="WS" + str(heute.year)
    if not tag:
        tag = date.today()

    url="https://vpis.fh-swf.de/" + str(semester) + "/raum.php3?Standort=" + str(standort) + "&Tag=" + str(tag) + "&Template=XML"
    # return requests.get(url).content
    return(print(url))

#with open ('test.xml', 'wb') as f:
#    f.write(getXML("","","2021-04-30"))

def parseXML():
    #tree = ET.parse(getXML(""))
    raumbelegung = {}
    tree = ET.parse('test.xml')
    vpisResponseXML = tree.getroot()
    for activityXML in vpisResponseXML.findall('./activities/activity'):
        modulname=activityXML.find('./name').text
        veranstaltungstyp=activityXML.find('./activity-type').text
        activityDates=activityXML.findall('./activity-dates/activity-date')
        raeume=activityXML.findall('./activity-locations/activity-location')
        for raum in raeume:
            for activityDate in activityDates:
                datum=activityDate.get('date')
                start=activityDate.get('begin')
                ende=activityDate.get('end')
                #print("In {} findet am {} das Modul {} von {} bis {} als {} statt.".format(raum.text, datum, modulname, start, ende, veranstaltungstyp))
                
                # raumnummer1 => datum1 => uhrzeit1 => veranstaltung1
                #                          uhrzeit2 => veranstaltung2
                #                          uhrzeit3 => veranstaltung3
                #             => datum2 => uhrzeit1 => veranstaltung1
                #                          uhrzeit2 => veranstaltung2
                #             => datum3 => uhrzeit1 => veranstaltung1
                # raumnummer2 => datum1 => uhrzeit1 => veranstaltung1
    
    for raum in raumbelegung:
        for datum in raum:
            for uhrzeit in datum:
                print("{} -> {} -> {} -> {}".format(raum, datum, uhrzeit, uhrzeit[name]))

parseXML()