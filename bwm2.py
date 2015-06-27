#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Ein kleines Programm zur Anzeige der Bandbreiten-Nutzung von ethX und FritzBox sowie
# [optional] der Erreichbarkeit von Hosts und DLAN-Adaptern.
# D.Ahlgrimm, 2012-2014
#
# 18.03.2013: Update für wx-v2.9 (in FensterPositionAnpassen())
# 18.03.2013: Änderung des Alarms von "wx.media" nach "Shell-CMD ausführen"
# 25.03.2013: Option FRAME_NO_TASKBAR eingebaut (zusammen mit dem Tool "wmctrl" nutzbar)
# 05.08.2013: Umstellung auf fuenf Devolo-Adapter, die jetzt AVM-Adapter sind
# 04.01.2014: farbeKurveUeberlagerung zugefügt für "empfangen<senden"

# 31.10.2014: Fix für FRITZ!OS 06.20 eingebaut

import wx
import time
import socket
import threading
import subprocess
from Queue import Queue



# Daten der Fritzbox und der NIC
FRITZBOX_IP="192.168.178.1"
FRITZBOX_PORT=49000
ETH_IF="eth0"

# shell-cmd zum Abspielen einer Sounddatei
ALARM_CMD="env AUDIODRIVER=alsa play /home/dede/daten/ding.wav"

# Ort des DLAN-Scanners
DLANLIST="/home/dede/bin/dlanlist"

# die zu pingenden Hosts
IPS_TO_PING=["fb", "switch", "c2q", "t430", "i5", "rp1", "rp2", "bb", 
             "bt", "tobi", "t22", "mutti", "11w", "tablet"]

# das Konfig-File
cfgFile_g=".bwm2rc"

# auf True, wenn das Fenster nicht in der Taskbar erscheinen soll. Sonst auf False
FRAME_NO_TASKBAR=True



# ###########################################################
# Erreichbarkeit von Devolo-Dlan-Adaptern pruefen und melden.
# Der Refresh erfolgt automatisch alle 10 Sekunden per Thread.
# Die Funktion "online()" liefert die erreichbaren Adapter
# als Bitmuster (z.B. 1="Buero" oder 5=4+1="Buero und Tobi".
# Die Funktion "namen()" liefert die Kurznamen als Liste.
class Devolo():
  def __init__(self):
    # MAC-Adressen der Devolo-Adapter samt Bit-Kennung
#    self.macs=[ ["00:0B:3B:58:CA:48", 1],   # Buero
#                ["00:0B:3B:16:38:CD", 2],   # Ferkelchen
#                ["00:0B:3B:16:38:D4", 4],   # Tobi
#                ["00:0B:3B:58:CA:53", 8]]   # unzugeordnet
#    self.kurznamen=["B", "M", "T", "?"]

    self.macs=[ ["C0:25:06:D0:36:18", 1],   # Buero
                ["BC:05:43:0B:31:59", 2],   # Ferkelchen
                ["C0:25:06:D0:36:17", 4],   # Tobi
                ["24:65:11:C4:01:CB", 8],   # Wohnzimmer WLAN
                ["BC:05:43:0B:31:5A",16]]   # Einspeisung
    self.kurznamen=["B", "M", "T", "W", "i"]


    # dlanlist von:
    # http://www.devolo.com/downloads/software/software-dlan-linux-v6-1.tar.gz
    # Der dlanlist muss mit "setcap cap_net_raw+epi" aufgemacht werden
    # aus Paket "libcap-progs - Libcap utility programs"
    self.cmd=[DLANLIST, ETH_IF]

    self.is_online=0
    self.abschalten=False

    worker=threading.Thread(target=self.__devolo_dlan, name="Devolo")
    worker.setDaemon(True)
    worker.start()

  # ###########################################################
  # Sagt dem Thread, dass er Feierabend hat.
  def Abschalten(self):
    self.abschalten=True

  # ###########################################################
  # Liefert die erreichbaren Dlan-Adapter als Bitmuster (int).
  def online(self):
    return(self.is_online)

  # ###########################################################
  # Liefert die Namens-Kenner fuer die Dlan-Adapter.
  def namen(self):
    return(self.kurznamen)

  # ###########################################################
  # Sucht im Netz nach eingeschalteten dLAN-Adaptern und
  # setzt "self.is_online" entsprechend der aktiven Adapter.
  def __devolo_dlan(self):
    while True:
      process=subprocess.Popen(self.cmd, shell=False, stdout=subprocess.PIPE)
      rc=process.communicate()[0]
      # Liefert sowas wie:
      # Type    MAC address        Mbps TX/RX       Version/Product
      # local   00:0B:3B:16:38:CD  ---.-- / ---.--  devolo AG dLAN HS Ethernet (MAC 1.6)
      # remote  00:0B:3B:58:CA:48   75.43 / ---.--  devolo AG dLAN HS Ethernet (MAC 1.6)
      #
      # oder fuer AVM Powerline:
      # Type    MAC address        Mbps TX/RX       Version/Product
      # local   C0:25:06:D0:36:18  ---.-- / ---.--  INT7400-MAC-5-2-5245-03-1296-20120918-FINAL-D AVM Powerline 500E T
      # remote  24:65:11:C4:01:CB  177.19 / 124.69  MAC-QCA7420-1.1.0.871-04-20130410-FINAL
      # oder auch:
      # no devices found
      is_online=0
      for j in self.macs:
        if rc.find(j[0])>0:
          is_online+=j[1]
      self.is_online=is_online
      for i in range(10):       # Check-Intervall = 10 Sekunden
        time.sleep(1)
        if self.abschalten==True:
          return





# ###########################################################
# Pingt im 30-Sekunden-Takt alle Hosts an, die in der Liste
# "ips" enthalten sind. Die aktuell erreichbaren Hosts werden
# mit der Funktion "Online()" abgefragt.
class Pinger():
  def __init__(self, ips):
    self.abschalten=False
    self.queue=Queue()  # Uebergabe an pinger()
    self.temp_list=[]
    self.onlinelist=[]  # Hostnamen der erreichbaren Systeme
    for i in range(4):  # vier Ping-Worker aufsetzen
      worker=threading.Thread(target=self.__pinger, name="Pinger("+str(i)+")")
      worker.setDaemon(True)
      worker.start()
    worker=threading.Thread(target=self.__update, name="PingerUpdate", args=(ips, )) # den Update-Worker aufsetzen
    worker.setDaemon(True)
    worker.start()

  # ###########################################################
  # Sagt den Threads, dass sie Feierabend haben.
  def Abschalten(self):
    self.abschalten=True

  # ###########################################################
  # Liefert die Liste der erreichbaren Systeme.
  def Online(self):
    return(self.onlinelist)

  # ###########################################################
  # Pingt alle Hosts aus der Liste "ips" an und kopiert danach
  # "self.temp_list" nach "self.onlinelist".
  def __update(self, ips):
    while True:
      self.temp_list=[]
      for ip in ips:
        self.queue.put(ip)
      self.queue.join()
      self.onlinelist=self.temp_list
      for i in range(30):           # Check-Intervall = 30 Sekunden
        time.sleep(1)
        if self.abschalten==True:
          for j in range(4):  # alle vier __pinger in den Feierabend schicken
            self.queue.put("0.0.0.0")
          return

  # ###########################################################
  # Pingt einen Hosts aus "self.queue" an und erweitert
  # "self.onlinelist" um den Host, wenn dieser geantwortet hat.
  def __pinger(self):
    while True:
      ip=self.queue.get()
      if ip=="0.0.0.0":
        return
      ret=subprocess.call("ping -c 1 {ip}".format(ip=ip), shell=True,
                           stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)
      if ret==0:
        self.temp_list.append(ip)
      self.queue.task_done()





# ###########################################################
# Bandbreiten-Informationen aus der Fritzbox auslesen.
class Fritzbox():
  def __init__(self, host=FRITZBOX_IP, port=FRITZBOX_PORT):
    self.host=host
    self.port=port

    self.controlURL= "upnp/control/WANCommonIFC1"
    self.serviceType="WANCommonInterfaceConfig:1"
    s=self.__send_req_resp("GetAddonInfos")
    if s.find("<faultstring>UPnPError</faultstring>")>=0:
      self.controlURL= "igdupnp/control/WANCommonIFC1"  # Fix für >= FRITZ!OS 06.20

  # ###########################################################
  # Sendet eine Anfrage an die Fritzbox und liefert den
  # Antwortstring zurueck
  def __send_req_resp(self, action):
    body='<?xml version="1.0"?>\n' \
         '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/"\n' \
         ' s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">\n' \
         '  <s:Body>\n' \
         '    <u:'+action+' xmlns:u="urn:schemas-upnp-org:service:'+self.serviceType+'"/>\n' \
         '  </s:Body>\n' \
         '</s:Envelope>\n'
    pream='POST /'+self.controlURL+' HTTP/1.0\r\n' \
          'HOST: '+self.host+':'+str(self.port)+'\r\n' \
          'CONTENT-LENGTH: '+str(len(body))+'\r\n' \
          'CONTENT-TYPE: text/xml; charset="utf-8"\r\n' \
          'SOAPACTION: "urn:schemas-upnp-org:service:'+self.serviceType+'#'+action+'"\r\n\r\n'
    sock=socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((self.host, self.port))
    sock.send(pream + body)

    resp = ""
    while True:
      data=sock.recv(1024)
      if len(data)==0:
        break
      resp+=data
    sock.close()
    return(resp)

  # ###########################################################
  # liefert aus "xml_str" den Teilstring, der zwischen
  #  <"arg"> und </"arg"> steht.
  def __get_argument(self, xml_str, arg):
    v="<"+arg+">"
    p1=xml_str.find(v)
    if p1>=0:
      p2=xml_str.find("</"+arg+">", p1)
      if p2>=0:
        return(xml_str[p1+len(v):p2])
    return(None)

  # ###########################################################
  # Liefert die Maximal-Werte der Verbindung.
  def Maximalwerte(self, div=1):
    s=self.__send_req_resp("GetCommonLinkProperties")
    # /9 fuer "Bit/Sek" zu "Byte/Sek"
    maxSnd=int(self.__get_argument(s, "NewLayer1UpstreamMaxBitRate"))/9
    maxRec=int(self.__get_argument(s, "NewLayer1DownstreamMaxBitRate"))/9
    return((maxRec/div, maxSnd/div))

  # ###########################################################
  # Liefert die aktuellen Uebertragungsraten.
  def UebertragungsRate(self, div=1):
    s=self.__send_req_resp("GetAddonInfos")
    snd=int(self.__get_argument(s, "NewByteSendRate"))
    rec=int(self.__get_argument(s, "NewByteReceiveRate"))
    return((rec/div, snd/div))





# ###########################################################
# Bandbreiten-Informationen von ethX auslesen.
#
# pos=0     1           2         3    4    5    6     7          8           9        10      11   12   13   14    15      16
#interface: bytes       packets   errs drop fifo frame compressed multicast | bytes    packets errs drop fifo colls carrier compressed
#     eth0: 1339779969  998857    0    0    0    0     0          752         54799542 625934  0    0    0    0     1       0
#           rec_pos                                                           snd_pos
class eth_messen():
  def __init__(self, interface=ETH_IF, proc_net_dev="/proc/net/dev", rec_pos=1, snd_pos=9):
    self.proc_net_dev=proc_net_dev
    self.interface=interface
    self.rec_pos=rec_pos
    self.snd_pos=snd_pos
    self.letzterWert=self.__DatenHolen()

  # ###########################################################
  # Liefert eine Liste mit drei Werten:
  #  [timestamp, BytesUebertragen-receive, BytesUebertragen-transmit]
  def __DatenHolen(self):
    fl=open(self.proc_net_dev, "r")
    s=0
    r=0
    for ln in fl:
      ln=ln.strip()
      if ln.find(self.interface)==0:
        lnl=ln.split()
        r=long(lnl[self.rec_pos])
        s=long(lnl[self.snd_pos])
    fl.close()
    return([time.time(), r, s])

  # ###########################################################
  # Liefert die Uebertragungs-Rate anhand des letzten und des
  # aktuellen Wertes von BytesUebertragen.
  def UebertragungsRate(self, div=1):
    w=self.__DatenHolen()
    d=1/float(w[0]-self.letzterWert[0])
    r=(w[1]-self.letzterWert[1])*d
    s=(w[2]-self.letzterWert[2])*d
    self.letzterWert=w
    return([round(r/div, 2), round(s/div, 2)])





# ###########################################################
# Verwaltet eine Liste von "breite" Werten, die von links
# nach rechts mit "WertAufnehmen()" gefuellt wird. In die
# komplett gefuellte Liste werden die neuen Werte von rechts
# reingeschoben, der aelteste Wert ganz links wird geloescht.
# Der Inhalt der Liste wird ueber "ListeLiefern()" abgerufen.
# Geliefert wird eine Liste aus Koordinaten, die bei
# ("pos_x", "pos_y") ihren Null-Punkt haben und bei
# ("pos_x"+"breite", "pos_y"+"hoehe") enden.
class Kurve():
  def __init__(self, pos_x, pos_y, breite, hoehe, name="", maxval=None):
    self.pos_x =pos_x   # X-Koordinate der linken unteren Ecke
    self.pos_y =pos_y   # Y-Koordinate der linken unteren Ecke
    self.breite=breite  # Anzahl Pixel in der Horizontalen
    self.hoehe =hoehe   # Anzahl Pixel in der Vertikalen
    self.name  =name    # der Name der Kurve
    self.maxval=maxval  # Maximaler Y-Wert, der angenommen wird

    self.aktPos=0       # aktuelle Einfuegeposition
    self.Ywerte=[]      # die Liste der Y-Werte
    self.maximal=1      # Maximal-Wert in "Ywerte"
    self.maximalAufgerundet=(1, "1 B")
    self.konstant=0     # Zaehler fuer "Werte am Minimum"
    for x in range(breite):
      self.Ywerte.append(0) # init

  # ###########################################################
  # Liefert Position und Abmessungen der Kurve.
  def xywh(self):
    return([self.pos_x, self.pos_y, self.breite, self.hoehe])

  # ###########################################################
  # X- und Y-Koordinate der Kurve [neu] setzen.
  def PositionEinstellen(self, pos_x, pos_y):
    self.pos_x =pos_x   # X-Koordinate der linken unteren Ecke
    self.pos_y =pos_y   # Y-Koordinate der linken unteren Ecke

  # ###########################################################
  # Die Hoehe der Kurve [neu] setzen.
  def HoeheEinstellen(self, hoehe):
    self.hoehe=hoehe

  # ###########################################################
  # Die Breite der Kurve [neu] setzen.
  def BreiteEinstellen(self, breite):
    if self.breite>breite:
      d=self.breite-breite  # Kurve um "d" kleiner machen
      for i in range(d):
        self.Ywerte.pop(0)
      self.aktPos=max(self.aktPos-d, 0)
    elif self.breite<breite:
      d=breite-self.breite  # Kurve um "d" groesser machen
      for i in range(d):
        self.Ywerte.append(0)
    else:
      return  # Breite hat sich nicht veraendert

    self.maximal=max(self.Ywerte)
    self.maximalAufgerundet=self.__Aufrunden(self.maximal)
    self.breite=breite

  # ###########################################################
  # Einen Y-Wert ("wert") von rechts in die Liste reinschieben.
  # Ueber "glaetten_stufe" wird bestimmt, an wie viele der
  # alten Werte der aufzunehmende Wert angeglichen werden soll.
  # Mit "alarm" ==True wird bestimmt, ob die Funktion melden
  # soll, wenn die Werte 5x hintereinander unterhalb von 1%
  # des Maximums lagen.
  def WertAufnehmen(self, wert, glaetten_stufe=0, alarm=False):
    rc=0

    if self.maxval!=None and wert>self.maxval:
      wert=self.maxval

    if self.aktPos<self.breite:     # wenn Liste noch nicht ganz voll ist
      if glaetten_stufe>0:          # ...per Index aufnehmen
        wert=self.__Glaetten(self.aktPos-1, wert, glaetten_stufe)
      self.Ywerte[self.aktPos]=wert
      self.aktPos+=1
    else:                           # ...sonst reinschieben
      w=self.Ywerte.pop(0)
      if w==self.maximal:             # wenn derzeitiger Maximal-Wert rausgeschoben wurde
        self.maximal=max(self.Ywerte) # ...dann neuen Maximal-Wert suchen
        self.maximalAufgerundet=self.__Aufrunden(self.maximal)
      if glaetten_stufe>0:
        wert=self.__Glaetten(self.aktPos-2, wert, glaetten_stufe)
      self.Ywerte.append(wert)

    if alarm==True and self.aktPos>1:
      proz_max=100.0/self.maximal*(self.Ywerte[self.aktPos-1] + self.Ywerte[self.aktPos-2])/2
      if proz_max<1.0:            # wenn Bandbreite unterhalb 1% des Maximums...
        self.konstant+=1
        if self.konstant>4:       # ...und das 5x hintereinander so ist...
          rc=1                    # ...dann Kenner fuer "Sound spielen" zurueckliefern
      else:
        self.konstant=0

    if wert>self.maximal:
      self.maximal=wert
      self.maximalAufgerundet=self.__Aufrunden(self.maximal)
    return(rc)

  # ###########################################################
  # Liefert den geglaetteten Wert von "wert", indem er als
  # Mittelwert der letzten "stufe" Werte zurueckgegeben wird.
  # Der juengste alte Wert befindet sich am Index "maxidx".
  def __Glaetten(self, maxidx, wert, stufe):
    anz=max(0, min(maxidx, stufe))
    w=0
    for i in range(anz):
      w+=self.Ywerte[maxidx-i]
    w+=wert
    return(w/(anz+1))

  # ###########################################################
  # Den Inhalt der Liste um X-Werte erweitern und als
  # Koordinaten-Liste zurueckgeben.
  # Die Y-Werte werden so skaliert, dass der groesste Y-Wert
  # der Liste unterhalb von "max_y" landet.
  # Die Koordinaten-Liste liegt immer zwischen den Eckpunkten
  # der Null-Linie - so dass sie als gefuelltes Polygon
  # dargestellt werden kann.
  def ListeLiefern(self, max_y):
    l=[(self.pos_x, self.pos_y)]                      # links unten
    for x in range(self.breite):
      l.append((x+self.pos_x, self.pos_y-max(min(self.Ywerte[x]*self.hoehe/max_y, self.hoehe), 0)))
    l.append((self.breite-1+self.pos_x, self.pos_y))  # rechts unten
    return(l)

  # ###########################################################
  # Liefert den groessten Wert aus der Liste als Liste mit drei
  # Elementen:
  #  [Maximal-Wert, aufgerundeter Maximal-Wert, aufgerundeter Maximal-Wert mit Faktor (B/KB/MB/GB)]
  def MaximalwertLiefern(self):
    return((self.maximal, self.maximalAufgerundet[0], self.maximalAufgerundet[1]))

  # ###########################################################
  # Liefert ein Raster fuer die Kurve als Input fuer DrawLineList.
  def RasterLiefern(self):
    r=[]
    for i in [0.25, 0.5, 0.75, 1]:
      r.append([self.pos_x, self.pos_y-(self.hoehe*i), self.pos_x+self.breite, self.pos_y-(self.hoehe*i)])
    for i in range(self.pos_x+self.breite, self.pos_x, -60):
      r.append([i, self.pos_y+5, i, self.pos_y-self.hoehe])
    return(r)

  # ###########################################################
  # Liefert den Namen der Kurve
  def NameLiefern(self):
    return(self.name)

  # ###########################################################
  # Liefert den aufgerundeten Betrag von "z" als Liste mit
  # zwei Werten. Der erste Wert entaelt den Betrag als Zahl, 
  # der zweite als String mit Groessen-Faktor (B/KB/MB/GB).
  def __Aufrunden(self, z):
    k=z
    f=0
    while k>1024:
      k/=1024
      f+=1
    fd=[100, 5, 1, 1]
    fe=["B", "KB", "MB", "GB"]
    e=((k//fd[f])+1)*fd[f]
    r=e
    for i in range(f):
      r*=1024
    return([int(r), str(e) + " " + fe[f]])





# ###########################################################
# Liefert "num" in der passendsten Groessenangabe
def prettySize(num):
  for x in ['','KB','MB','GB', 'TB']:
    if num<1024.0:
      return("{0:3.0f} {1:s}".format(num, x))
    num/=1024.0





ABSTAND_X=10          # Pixel links und rechts von der Kurve
ABSTAND_Y=20          # Pixel ueber der Grafik/Text-Ausgabe (bzw. Hoehe der Kopfzeile des Fensters)
RAND_UNTEN=5          # Pixel unter der Kurve bzw. der Pinger-Anzeige
INFO_BEREICH_DLAN=25  # Breite des DLAN-Info-Bereichs

# ###########################################################
# Das Fenster.
class Bwm2Panel(wx.Window):
  def __init__(self, parent):
    wx.Window.__init__(self, parent)

    self.alarm=False

    self.parent=parent
    self.SetBackgroundStyle(wx.BG_STYLE_CUSTOM)
    self.Bind(wx.EVT_PAINT, self.on_paint)

    self.MenueErstellen()
    self.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

    self.KonfigEinlesen()

    self.Bind(wx.EVT_TIMER, self.on_timer)
    self.timer=wx.Timer(self)
    self.timer.Start(self.updateIntervall)

    self.basis_x=ABSTAND_X
    self.basis_y=ABSTAND_Y+self.hoehe

    # k1 ist die ethX-Empfangs-Kurve. Sie wird rechts von der Fritzbox-Kurve dargestellt.
    # Die Daten von ethX werden auch bei abgeschalteter Anzeige gelesen. Dadurch liegen sie
    # bereits vor, wenn man die Kurve nachtraeglich zuschaltet.
    self.ethX=eth_messen(ETH_IF)
    self.k1=Kurve(self.basis_x+self.breite+ABSTAND_X, self.basis_y, self.breite, self.hoehe, ETH_IF)
    if self.kurven_uebereinander==True:
      self.k2=Kurve(self.basis_x+self.breite+ABSTAND_X, self.basis_y                     , self.breite, self.hoehe)
    else:
      self.k2=Kurve(self.basis_x+self.breite+ABSTAND_X, self.basis_y+self.hoehe+ABSTAND_Y, self.breite, self.hoehe)

    # k3 ist die Fritzbox-Empfangs-Kurve. Sie wird ganz links im Fenster dargestellt.
    self.fb=Fritzbox()
    r, s=self.fb.Maximalwerte()
#    if s==0 and r==0:
#      s=500000
#      r=5000000
#    self.k3=Kurve(self.basis_x, self.basis_y, self.breite, self.hoehe, \
#                  "Fritzbox (" + prettySize(r) + " / " + prettySize(s) + ")", maxval=(r*2))
    if s==0 and r==0: # wenn Fritzbox als Router konfiguriert ist....gibts keine Maximalwerte
      self.k3=Kurve(self.basis_x, self.basis_y, self.breite, self.hoehe, "Fritzbox")
    else:
      self.k3=Kurve(self.basis_x, self.basis_y, self.breite, self.hoehe, \
                    "Fritzbox (" + prettySize(r) + " / " + prettySize(s) + ")", maxval=(r*2))

    if self.kurven_uebereinander==True:
      if s==0 and r==0:
        self.k4=Kurve(self.basis_x, self.basis_y                     , self.breite, self.hoehe)
      else:
        self.k4=Kurve(self.basis_x, self.basis_y                     , self.breite, self.hoehe, maxval=(s*2))
    else:
      if s==0 and r==0:
        self.k4=Kurve(self.basis_x, self.basis_y+self.hoehe+ABSTAND_Y, self.breite, self.hoehe)
      else:
        self.k4=Kurve(self.basis_x, self.basis_y+self.hoehe+ABSTAND_Y, self.breite, self.hoehe, maxval=(s*2))

    # Wenn die Devolo-Status-Anzeige abgeschaltet ist, erfolgt auch kein Polling der Adapter.
    if self.dlan_anzeigen==True:
      self.devolo=Devolo()
      self.devolo_online=0

    # Wenn die Pinger-Anzeige abgeschaltet ist, werden auch keine Systeme angepingt.
    self.ips=IPS_TO_PING
    if self.pinger_anzeigen==True:
      self.pinger=Pinger(self.ips)
    
    self.hoehePingerBereich=20      # wird bei Bedarf in "FensterPositionAnpassen" gesetzt
    self.laengsterHostname=None     # wird bei Bedarf in "on_paint" vor der ersten Nutzung gesetzt

    self.dc=None
    wx.CallLater(50, self.WarteAufDC) # "on_paint" muss gelaufen sein

  # ###########################################################
  # Ruft sich so lange selbst wieder auf, bis "self.dc" in
  # "on_paint" gesetzt wurde, um dann FensterPositionAnpassen
  # aufzurufen.
  def WarteAufDC(self):
    if self.dc==None:
      wx.CallLater(50, self.WarteAufDC)
    else:
      self.FensterPositionAnpassen()

  # ###########################################################
  # Konfig-File einlesen und Werte entsprechend einstellen.
  def KonfigEinlesen(self):
    fc=wx.FileConfig(localFilename=cfgFile_g)
    self.kurven_uebereinander=    fc.ReadInt("KurvenUebereinander", 1)
    self.updateIntervall=         fc.ReadInt("UpdateIntervall", 1000)
    self.hoehe=                   fc.ReadInt("KurvenHoehe", 60)
    self.breite=                  fc.ReadInt("KurvenBreite", 300)
    self.glaettung=               fc.ReadInt("Glaettung", 0)
    self.dlan_anzeigen=           fc.ReadInt("dlanAnzeigen", 0)
    self.pinger_anzeigen=         fc.ReadInt("PingerAnzeigen", 0)
    self.ethX_anzeigen=           fc.ReadInt("ethXAnzeigen", 1)
    self.farbeEmpfangsKurve=      fc.Read("farbeEmpfangsKurve"     , "#0000FF")
    self.farbeSendeKurve=         fc.Read("farbeSendeKurve"        , "#FFFF00")
    self.farbeKurveUeberlagerung= fc.Read("farbeKurveUeberlagerung", "#E991AA")
    self.farbeHintergrund=        fc.Read("farbeHintergrund"       , "#CCCCCC")
    self.farbeRaster=             fc.Read("farbeRaster"            , "#FFFFFF")
    self.farbeSchrift=            fc.Read("farbeSchrift"           , "#000000")

  # ###########################################################
  # Stellt das Kontext-Menue dar.
  def OnContextMenu(self, event):
    self.PopupMenu(self.menue)

  # ###########################################################
  # Legt das Kontext-Menue an.
  def MenueErstellen(self):
    self.menue=wx.Menu()
    self.menue.Append(100, 'Einstellungen ändern')
    self.menue.Append(101, 'Einstellungen speichern')
    self.menue.AppendSeparator()
    self.menue.Append(102, 'Alarm', '', True)
    self.menue.Append(109, 'debug')
    self.menue.AppendSeparator()
    self.menue.Append(108, 'Über das Programm')

    self.menue.Check(102, self.alarm)

    self.Bind(wx.EVT_MENU, self.KonfigAendern, id=100)
    self.Bind(wx.EVT_MENU, self.KonfigSchreiben, id=101)
    self.Bind(wx.EVT_MENU, self.Alarm, id=102)
    self.Bind(wx.EVT_MENU, self.debug, id=109)
    self.Bind(wx.EVT_MENU, self.UeberGewaehlt, id=108)

  # ###########################################################
  #
  def debug(self, event):
    print threading.enumerate()

  # ###########################################################
  # Setzt "self.alarm" gemaess Menue-Auswahl und spielt den
  # Sound einmal ab, wenn der Alarm eingeschaltet wurde.
  def Alarm(self, event):
    self.alarm=self.menue.IsChecked(102)
    if self.alarm==True:
      subprocess.call(ALARM_CMD, shell=True, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)

  # ###########################################################
  # Fenster-Position/Groesse den geaenderten Anzeige-Elementen
  # anpassen.
  def FensterPositionAnpassen(self):
    ax, ay=self.parent.GetScreenPositionTuple()
    aw, ah=self.parent.GetSizeTuple()

    iw, ih=self.parent.GetClientRect().GetSize()  # innere Fenster-Abmessungen
    ds=(aw-iw, ah-ih)                             # Abmessungen der Fenster-Dekoration

    ibd=0
    if self.dlan_anzeigen==True:          ibd=INFO_BEREICH_DLAN # bei Bedarf Platz reservieren
    if self.ethX_anzeigen==True:          w=self.basis_x + 2*self.breite + 2*ABSTAND_X + ibd
    else:                                 w=self.basis_x +   self.breite +   ABSTAND_X + ibd
    if self.pinger_anzeigen==True:        self.hoehePingerBereich=self.HoehePingerBereich(w)
    else:                                 self.hoehePingerBereich=0
    if self.kurven_uebereinander==True:   h=self.basis_y + RAND_UNTEN                          + self.hoehePingerBereich
    else:                                 h=self.basis_y + RAND_UNTEN + ABSTAND_Y + self.hoehe + self.hoehePingerBereich
    self.parent.SetSize((w+ds[0], h+ds[1])) # Groesse des Fensters setzen

    dx=aw-w-ds[0] # Ausdehung des Fensters entsprechend der Bildschirm-Ecke, in der sich das Fenster befindet
    dy=ah-h-ds[1]
    links, oben, rechts, unten=wx.Display().GetGeometry()

    if ax==0 and ay==0:                               self.parent.Move((ax, ay))        # links oben
    if ax==0 and (ay+ah)>(unten-100):                 self.parent.Move((ax, ay+dy))     # links unten
    if (ax+aw)>(rechts-100) and ay==0:                self.parent.Move((ax+dx, ay))     # rechts oben
    if (ax+aw)>(rechts-100) and (ay+ah)>(unten-100):  self.parent.Move((ax+dx, ay+dy))  # rechts unten

  # ###########################################################
  # Oeffnet den Einstellungs-Dialog und verarbeitet danach ggf.
  # die Aenderungen an den Konfigurations-Parametern.
  def KonfigAendern(self, event):
    d=EinstellungsDialog( self, self.updateIntervall, self.hoehe, self.breite, \
                          self.glaettung, self.dlan_anzeigen, self.pinger_anzeigen, self.ethX_anzeigen, \
                          self.kurven_uebereinander, self.farbeEmpfangsKurve, self.farbeSendeKurve, \
                          self.farbeKurveUeberlagerung, \
                          self.farbeHintergrund, self.farbeRaster, self.farbeSchrift)
    if d.ShowModal()==wx.ID_OK:
      r=d.GetValues()
      hoehe_oder_breite_geaendert=0
      if self.updateIntervall!=r[0]:
        self.updateIntervall=r[0]               # updateIntervall
        self.timer.Stop()
        self.timer.Start(self.updateIntervall)

      if self.hoehe!=r[1]:
        self.hoehe=r[1]                         # kurvenHoehe
        self.k1.HoeheEinstellen(self.hoehe)
        self.k2.HoeheEinstellen(self.hoehe)
        self.k3.HoeheEinstellen(self.hoehe)
        self.k4.HoeheEinstellen(self.hoehe)
        hoehe_oder_breite_geaendert=1

      if self.breite!=r[2]:
        self.breite=r[2]                        # kurvenBreite
        self.k1.BreiteEinstellen(self.breite)
        self.k2.BreiteEinstellen(self.breite)
        self.k3.BreiteEinstellen(self.breite)
        self.k4.BreiteEinstellen(self.breite)
        hoehe_oder_breite_geaendert=1

      if hoehe_oder_breite_geaendert==1:
        self.basis_y=ABSTAND_Y+self.hoehe
        # k2 und k4 werden unten entsprechend "kurven_uebereinander" eingestellt
        self.k1.PositionEinstellen(self.basis_x+self.breite+ABSTAND_X, self.basis_y)
        self.k3.PositionEinstellen(self.basis_x, self.basis_y)

      self.glaettung=           r[3]            # glaettung

      if self.dlan_anzeigen!=r[4]:
        self.dlan_anzeigen=r[4]                 # dlan_anzeigen
        if self.dlan_anzeigen==True:
          self.devolo=Devolo()
          self.devolo_online=0
        else:
          self.devolo.Abschalten()
          del self.devolo

      if self.pinger_anzeigen!=r[5]:
        self.pinger_anzeigen=r[5]               # pinger_anzeigen
        if self.pinger_anzeigen==True:
          self.pinger=Pinger(self.ips)
        else:
          self.pinger.Abschalten()
          del self.pinger

      self.ethX_anzeigen=           r[6]            # ethX_anzeigen
      self.kurven_uebereinander=    r[7]            # kurven_uebereinander
      self.farbeEmpfangsKurve=      r[8]            # farbeEmpfangsKurve
      self.farbeSendeKurve=         r[9]            # farbeSendeKurve
      self.farbeKurveUeberlagerung= r[10]           # farbeKurveUeberlagerung
      self.farbeHintergrund=        r[11]           # farbeHintergrund
      self.farbeRaster=             r[12]           # farbeRaster
      self.farbeSchrift=            r[13]           # farbeSchrift

      if self.kurven_uebereinander==True:
        self.k2.PositionEinstellen(self.basis_x+self.breite+ABSTAND_X, self.basis_y)
        self.k4.PositionEinstellen(self.basis_x, self.basis_y)
      else:
        self.k2.PositionEinstellen(self.basis_x+self.breite+ABSTAND_X, self.basis_y+self.hoehe+ABSTAND_Y)
        self.k4.PositionEinstellen(self.basis_x, self.basis_y+self.hoehe+ABSTAND_Y)
    d.Destroy()
    self.FensterPositionAnpassen()

  # ###########################################################
  # Speichert die Groesse und Position des Fensters im
  # Konfig-File.
  def KonfigSchreiben(self, event):
    fc=wx.FileConfig(localFilename=cfgFile_g)
    sp=self.parent.GetScreenPosition()
    ss=self.parent.GetSizeTuple()

    fc.WriteInt("pos_x",  sp[0])
    fc.WriteInt("pos_y",  sp[1])
    fc.WriteInt("size_x", ss[0])
    fc.WriteInt("size_y", ss[1])
    fc.WriteInt("KurvenUebereinander",  self.kurven_uebereinander)
    fc.WriteInt("UpdateIntervall",      self.updateIntervall)
    fc.WriteInt("KurvenHoehe",          self.hoehe)
    fc.WriteInt("KurvenBreite",         self.breite)
    fc.WriteInt("Glaettung",            self.glaettung)
    fc.WriteInt("dlanAnzeigen",         self.dlan_anzeigen)
    fc.WriteInt("PingerAnzeigen",       self.pinger_anzeigen)
    fc.WriteInt("ethXAnzeigen",         self.ethX_anzeigen)
    fc.Write("farbeEmpfangsKurve",      str(self.farbeEmpfangsKurve))
    fc.Write("farbeSendeKurve",         str(self.farbeSendeKurve))
    fc.Write("farbeKurveUeberlagerung", str(self.farbeKurveUeberlagerung))
    fc.Write("farbeHintergrund",        str(self.farbeHintergrund))
    fc.Write("farbeRaster",             str(self.farbeRaster))
    fc.Write("farbeSchrift",            str(self.farbeSchrift))
    fc.Flush()

  # ###########################################################
  # Menue: Ueber
  def UeberGewaehlt(self, event):
    info=wx.AboutDialogInfo()
    info.SetName("Bandbreiten-Monitor")
    info.SetVersion("2.01")
    info.SetCopyright("D.A.  (05/06.2012)")
    info.SetDescription("Ein kleines Programm zur Anzeige der Bandbreiten-Nutzung von ethX und FritzBox.")
    info.SetLicence("Dieses Programm ist freie Software gemaess GNU General Public License")
    info.AddDeveloper("Detlev Ahlgrimm")
    wx.AboutBox(info)

  # ###########################################################
  # Ruft einmal pro Update-Intervall die Anzeige-Update-Funktion
  # auf.
  def on_timer(self, event):
    self.update_drawing()

  # ###########################################################
  # Aktualisiert die internen Listen pro Update-Intervall, um
  # danach einen Fenster-Refresh einzuleiten, bei dem die
  # Updates an den Listen dargestellt werden.
  def update_drawing(self):
    r, s=self.ethX.UebertragungsRate()
    self.k1.WertAufnehmen(r, self.glaettung)
    self.k2.WertAufnehmen(s, self.glaettung)

    r, s=self.fb.UebertragungsRate()
    alarm=self.k3.WertAufnehmen(r, self.glaettung, self.alarm)
    self.k4.WertAufnehmen(s, self.glaettung)
    self.Refresh(False)

    if self.dlan_anzeigen==True:
      self.devolo_online=self.devolo.online()

    if alarm>0:
      subprocess.call(ALARM_CMD, shell=True, stdout=open('/dev/null', 'w'), stderr=subprocess.STDOUT)
      self.alarm=False
      self.menue.Check(102, self.alarm)

  # ###########################################################
  # Liefert aus den zwei übergebenen Kurven eine neue Kurve,
  # die der Überlagerung der beiden Kurven entspricht.
  def Ueberlagerung(self, l0, l1):
    d=[]
    for x in range(len(l0)):
      k=max(l0[x][1], l1[x][1])
      d.append((l0[x][0], k))
    return(d)

  # ###########################################################
  # Aktualisiert das Fenster.
  def on_paint(self, event):
    self.dc=wx.AutoBufferedPaintDC(self)
    self.dc.SetBackground(wx.Brush(self.farbeHintergrund))
    self.dc.Clear()

    # -----------------------------------------------------------
    # Raster zeichnen
    self.dc.SetPen(wx.Pen(self.farbeRaster))
    l=[]
    if self.ethX_anzeigen==True:
      l+=self.k1.RasterLiefern()    # Raster fuer ethX-Empfangen
    l+=self.k3.RasterLiefern()      # Raster fuer Fritzbox-Empfangen

    if self.kurven_uebereinander==False:
      if self.ethX_anzeigen==True:
        l+=self.k2.RasterLiefern()  # Raster fuer ethX-Senden
      l+=self.k4.RasterLiefern()    # Raster fuer Fritzbox-Senden
    self.dc.DrawLineList(l)

    # -----------------------------------------------------------
    # Kurven zeichnen
    self.dc.SetPen(wx.Pen(self.farbeEmpfangsKurve))
    self.dc.SetBrush(wx.Brush(self.farbeEmpfangsKurve))

    if self.ethX_anzeigen==True:
      if self.kurven_uebereinander==True:  # Kurven ueberlagert darstellen
        if self.k1.MaximalwertLiefern()[1]>self.k2.MaximalwertLiefern()[1]:
          m1=self.k1.MaximalwertLiefern()
        else:
          m1=self.k2.MaximalwertLiefern()
      else:
        m1=self.k1.MaximalwertLiefern()
      # m1 enthaelt jetzt den Maximal-Kurvenhoehe fuer k1 und ggf. k2 (ethX)
      l=self.k1.ListeLiefern(m1[1])
      self.dc.DrawPolygon(l)

    if self.kurven_uebereinander==True:  # Kurven ueberlagert darstellen
      if self.k3.MaximalwertLiefern()[1]>self.k4.MaximalwertLiefern()[1]:
        m3=self.k3.MaximalwertLiefern()
      else:
        m3=self.k4.MaximalwertLiefern()
    else:
      m3=self.k3.MaximalwertLiefern()
    # m3 enthaelt jetzt den Maximal-Kurvenhoehe fuer k3 und ggf. k4 (Fritzbox)
    l0=self.k3.ListeLiefern(m3[1])
    self.dc.DrawPolygon(l0)

    self.dc.SetPen(wx.Pen(self.farbeSendeKurve))
    self.dc.SetBrush(wx.Brush(self.farbeSendeKurve))

    if self.ethX_anzeigen==True:
      if self.kurven_uebereinander==True:  # Kurven ueberlagert darstellen
        m=m1  # Kurvenhoehe von k1
      else:
        m=self.k2.MaximalwertLiefern()
      l=self.k2.ListeLiefern(m[1])
      self.dc.DrawPolygon(l)

    if self.kurven_uebereinander==True:  # Kurven ueberlagert darstellen
      m=m3  # Kurvenhoehe von k3
    else:
      m=self.k4.MaximalwertLiefern()
    l1=self.k4.ListeLiefern(m[1])
    self.dc.DrawPolygon(l1)

    if self.kurven_uebereinander==True:  # Kurven ueberlagert darstellen
      self.dc.SetPen(wx.Pen(self.farbeKurveUeberlagerung))
      self.dc.SetBrush(wx.Brush(self.farbeKurveUeberlagerung))
      d=self.Ueberlagerung(l0, l1)
      self.dc.DrawPolygon(d)

    # -----------------------------------------------------------
    # Texte zeichen
    self.dc.SetTextForeground(self.farbeSchrift)
    if self.ethX_anzeigen==True:
      w, h=self.dc.GetTextExtent(self.k1.NameLiefern())
      y=self.k1.xywh()[1]-self.k1.xywh()[3]-h
      self.dc.DrawText(self.k1.NameLiefern(), self.k1.xywh()[0]+self.k1.xywh()[2]-w, y)
      self.dc.DrawText(m1[2], self.k1.xywh()[0], y)

    debugtxt="  (Threads="+str(threading.active_count())+")"
    w, h=self.dc.GetTextExtent(self.k3.NameLiefern())
    y=self.k3.xywh()[1]-self.k3.xywh()[3]-h
    self.dc.DrawText(self.k3.NameLiefern(), self.k3.xywh()[0]+self.k3.xywh()[2]-w, y)
    self.dc.DrawText(m3[2]+debugtxt, self.k3.xywh()[0], y)

    if self.kurven_uebereinander==False:  # Kurven einzeln darstellen
      if self.ethX_anzeigen==True:
        self.dc.DrawText(self.k2.MaximalwertLiefern()[2], self.k2.xywh()[0], self.k2.xywh()[1]-self.k2.xywh()[3]-h)
      self.dc.DrawText(self.k4.MaximalwertLiefern()[2], self.k4.xywh()[0], self.k4.xywh()[1]-self.k4.xywh()[3]-h)

    # -----------------------------------------------------------
    # Dlan-Info-Bereich
    if self.dlan_anzeigen==True:
      if self.ethX_anzeigen==True:          w=self.basis_x + 2*self.breite + 2*ABSTAND_X
      else:                                 w=self.basis_x +   self.breite +   ABSTAND_X
      if self.kurven_uebereinander==True:   h=self.basis_y
      else:                                 h=self.basis_y + ABSTAND_Y + self.hoehe

      bw, bh=self.dc.GetTextExtent("B")  # es geht nur um die Hoehe
      self.dc.SetPen(wx.Pen("BLACK"))
      #for i in range(4):
      for i in range(len(self.devolo.namen())):
        b=1<<i
        if self.devolo_online&b==b: self.dc.SetBrush(wx.Brush("YELLOW"))
        else:                       self.dc.SetBrush(wx.Brush(self.farbeHintergrund))
        self.dc.DrawCirclePoint((w, h-(5+15*i)), 5)
        self.dc.DrawText(self.devolo.namen()[i], w+10, h-(5+15*i)-bh/2)

    # -----------------------------------------------------------
    # Pinger-Info-Bereich
    if self.pinger_anzeigen==True:
      aw, ah=self.parent.GetSizeTuple()
      if self.kurven_uebereinander==True:   h=self.basis_y
      else:                                 h=self.basis_y + ABSTAND_Y + self.hoehe

      self.dc.SetPen(wx.Pen("BLACK"))
      nx=10
      ny=h+15
      ol=self.pinger.Online()
      if self.laengsterHostname==None:  # wird im __init__ auf None gesetzt
        self.laengsterHostname=self.LaengsterHostname()
      for i in self.ips:
        if i in ol: self.dc.SetBrush(wx.Brush("YELLOW"))
        else:       self.dc.SetBrush(wx.Brush(self.farbeHintergrund))
        if self.hoehePingerBereich==20:   # wenn einzeilig
          bw, bh=self.dc.GetTextExtent(i) # Breite jedes einzelnen Hostnamen unterschiedlich
        else:
          bw=self.laengsterHostname[0]    # wenn mehrzeilig: Breite des laengsten Hostnamen verwenden
          bh=self.laengsterHostname[1]
        if (nx+8+bw)>aw:
          ny+=15
          nx=10
        self.dc.DrawCirclePoint((nx, ny), 5)
        self.dc.DrawText(i, nx+8, ny-bh/2)
        nx=nx+8+bw+15

  # ###########################################################
  # Liefert die Breite und Hoehe des laengsten Namen in 
  # "self.ips" als Liste.
  def LaengsterHostname(self):
    m=0
    for i in self.ips:
      bw, bh=self.dc.GetTextExtent(i)
      m=max(m, bw)
    return([m, bh])

  # ###########################################################
  # Liefert die benoetigte Hoehe fuer den Pinger-Bereich.
  # Es werden die Breiten fuer einzeilig und mehrzeilig (also
  # mit gleicher Laenge fuer alle Hostnamen) durchgerechnet und
  # die platzsparendere Variante gewaehlt.
  def HoehePingerBereich(self, breite):
    nx1=nx2=10
    ny1=ny2=15
    self.laengsterHostname=self.LaengsterHostname()
    for i in self.ips:
      bw1, bh=self.dc.GetTextExtent(i) # einzeilig: Breite jedes einzelnen Hostnamen unterschiedlich
      bw2=self.laengsterHostname[0]    # mehrzeilig: Breite des laengsten Hostnamen verwenden
      if (nx1+8+bw1)>breite:  # Berechnung fuer einzeilig
        ny1+=15
        nx1=10
      nx1=nx1+8+bw1+15
      if (nx2+8+bw2)>breite:  # Berechnung fuer mehrzeilig
        ny2+=15
        nx2=10
      nx2=nx2+8+bw2+15
    if ny1==15: # passt einzeilig
      return(ny1+5)   # 20 (15+5) ist der Kenner fuer einzeilig
    return(ny2+5)





# ###########################################################
# Ein Dialog zum Aendern von Einstellungen
class EinstellungsDialog(wx.Dialog):
  def __init__( self, parent, updateIntervall, kurvenHoehe, kurvenBreite, glaettung, \
                dlan_anzeigen, pinger_anzeigen, ethX_anzeigen, kurven_uebereinander, farbeEmpfangsKurve, \
                farbeSendeKurve, farbeKurveUeberlagerung, farbeHintergrund, farbeRaster, farbeSchrift):
    super(EinstellungsDialog, self).__init__(parent=parent, title="Einstellungen")

    st11=wx.StaticText(self, label="Update-Intervall [ms]:")
    self.updateIntervall=wx.SpinCtrl(self, wx.ID_ANY, "1000", size=(90, -1), min=500, max=10000)
    self.updateIntervall.SetValue(updateIntervall)
    self.updateIntervall.SetToolTip(wx.ToolTip('500 - 10.000'))

    st12=wx.StaticText(self, label="Kurven-Höhe [Pixel]:")
    self.kurvenHoehe=wx.SpinCtrl(self, wx.ID_ANY, "70", size=(70, -1), min=10, max=200)
    self.kurvenHoehe.SetValue(kurvenHoehe)
    self.kurvenHoehe.SetToolTip(wx.ToolTip('10 - 200'))

    st13=wx.StaticText(self, label="Kurven-Breite [Pixel]:")
    self.kurvenBreite=wx.SpinCtrl(self, wx.ID_ANY, "300", size=(70, -1), min=200, max=500)
    self.kurvenBreite.SetValue(kurvenBreite)
    self.kurvenBreite.SetToolTip(wx.ToolTip('200 - 500'))

    st14=wx.StaticText(self, label="Glättungswert [Werte]:")
    self.glaettung=wx.SpinCtrl(self, wx.ID_ANY, "0", size=(40, -1), min=0, max=5)
    self.glaettung.SetValue(glaettung)
    self.glaettung.SetToolTip(wx.ToolTip('0 - 5'))

    self.dlan_anzeigen=wx.CheckBox(self, label="Dlan-Monitor")
    self.dlan_anzeigen.SetValue(dlan_anzeigen)

    self.pinger_anzeigen=wx.CheckBox(self, label="Ping-Monitor")
    self.pinger_anzeigen.SetValue(pinger_anzeigen)

    self.ethX_anzeigen=wx.CheckBox(self, label=ETH_IF+" anzeigen")
    self.ethX_anzeigen.SetValue(ethX_anzeigen)

    self.kurven_uebereinander=wx.CheckBox(self, label="Kurven übereinander")
    self.kurven_uebereinander.SetValue(kurven_uebereinander)

    st15=wx.StaticText(self, label="Farbe Empfangs-Kurve:")
    self.farbeEmpfangsKurve=wx.ColourPickerCtrl(self, wx.ID_ANY)
    self.farbeEmpfangsKurve.SetColour(farbeEmpfangsKurve)

    st16=wx.StaticText(self, label="Farbe Sende-Kurve:")
    self.farbeSendeKurve=wx.ColourPickerCtrl(self, wx.ID_ANY)
    self.farbeSendeKurve.SetColour(farbeSendeKurve)

    st20=wx.StaticText(self, label="Farbe Überlagerung:")
    self.farbeKurveUeberlagerung=wx.ColourPickerCtrl(self, wx.ID_ANY)
    self.farbeKurveUeberlagerung.SetColour(farbeKurveUeberlagerung)

    st17=wx.StaticText(self, label="Hintergrund-Farbe:")
    self.farbeHintergrund=wx.ColourPickerCtrl(self, wx.ID_ANY)
    self.farbeHintergrund.SetColour(farbeHintergrund)

    st18=wx.StaticText(self, label="Raster-Farbe:")
    self.farbeRaster=wx.ColourPickerCtrl(self, wx.ID_ANY)
    self.farbeRaster.SetColour(farbeRaster)

    st19=wx.StaticText(self, label="Schrift-Farbe:")
    self.farbeSchrift=wx.ColourPickerCtrl(self, wx.ID_ANY)
    self.farbeSchrift.SetColour(farbeSchrift)

    ok=     wx.Button(self, wx.ID_OK,     "Ok")
    abbruch=wx.Button(self, wx.ID_CANCEL, "Abbruch")
    ok.SetDefault()

    sizer=wx.GridBagSizer()

    flag=wx.ALIGN_CENTER_VERTICAL|wx.ALL
    border=5
    # size(x, y)    pos(y, x)    span(y, x)
    sizer.Add(st11,                         pos=(0, 0), flag=flag, border=border)
    sizer.Add(self.updateIntervall,         pos=(0, 1), flag=flag, border=border)
    sizer.Add(st12,                         pos=(1, 0), flag=flag, border=border)
    sizer.Add(self.kurvenHoehe,             pos=(1, 1), flag=flag, border=border)
    sizer.Add(st13,                         pos=(2, 0), flag=flag, border=border)
    sizer.Add(self.kurvenBreite,            pos=(2, 1), flag=flag, border=border)
    sizer.Add(st14,                         pos=(3, 0), flag=flag, border=border)
    sizer.Add(self.glaettung,               pos=(3, 1), flag=flag, border=border)
    sizer.Add(self.dlan_anzeigen,           pos=(4, 1), flag=flag, border=border)
    sizer.Add(self.pinger_anzeigen,         pos=(5, 1), flag=flag, border=border)
    sizer.Add(self.ethX_anzeigen,           pos=(6, 1), flag=flag, border=border)
    sizer.Add(self.kurven_uebereinander,    pos=(7, 1), flag=flag, border=border)
    sizer.Add(st15,                         pos=(8, 0), flag=flag, border=border)
    sizer.Add(self.farbeEmpfangsKurve,      pos=(8, 1), flag=flag, border=border)
    sizer.Add(st16,                         pos=(9, 0), flag=flag, border=border)
    sizer.Add(self.farbeSendeKurve,         pos=(9, 1), flag=flag, border=border)
    sizer.Add(st20,                         pos=(10, 0), flag=flag, border=border)
    sizer.Add(self.farbeKurveUeberlagerung, pos=(10, 1), flag=flag, border=border)

    sizer.Add(st17,                         pos=(11, 0), flag=flag, border=border)
    sizer.Add(self.farbeHintergrund,        pos=(11, 1), flag=flag, border=border)
    sizer.Add(st18,                         pos=(12, 0), flag=flag, border=border)
    sizer.Add(self.farbeRaster,             pos=(12, 1), flag=flag, border=border)
    sizer.Add(st19,                         pos=(13, 0), flag=flag, border=border)
    sizer.Add(self.farbeSchrift,            pos=(13, 1), flag=flag, border=border)

    sizer.Add(wx.StaticLine(self),          pos=(14, 0), span=(1, 2), flag=wx.ALL|wx.GROW, border=5)
    sizer.Add(ok,                           pos=(15, 0), flag=flag, border=border)
    sizer.Add(abbruch,                      pos=(15, 1), flag=flag, border=border)
    
    self.SetSizerAndFit(sizer)
    self.Center()
    abbruch.SetFocus()

  # ###########################################################
  # Liefert saemtliche einstellbaren Werte des Dialoges als
  # Liste.
  def GetValues(self):
    ek=self.farbeEmpfangsKurve.GetColour()
    sk=self.farbeSendeKurve.GetColour()
    uk=self.farbeKurveUeberlagerung.GetColour()
    hf=self.farbeHintergrund.GetColour()
    rf=self.farbeRaster.GetColour()
    sf=self.farbeSchrift.GetColour()
    return([self.updateIntervall.GetValue(),      \
            self.kurvenHoehe.GetValue(),          \
            self.kurvenBreite.GetValue(),         \
            self.glaettung.GetValue(),            \
            self.dlan_anzeigen.GetValue(),        \
            self.pinger_anzeigen.GetValue(),      \
            self.ethX_anzeigen.GetValue(),        \
            self.kurven_uebereinander.GetValue(), \
            ek.GetAsString(wx.C2S_HTML_SYNTAX),   \
            sk.GetAsString(wx.C2S_HTML_SYNTAX),   \
            uk.GetAsString(wx.C2S_HTML_SYNTAX),   \
            hf.GetAsString(wx.C2S_HTML_SYNTAX),   \
            rf.GetAsString(wx.C2S_HTML_SYNTAX),   \
            sf.GetAsString(wx.C2S_HTML_SYNTAX) ])





# ###########################################################
# Der Fenster-Rahmen fuer das Hauptfenster.
class Bwm2Frame(wx.Frame):
  def __init__(self, parent, pos=wx.DefaultPosition, size=wx.DefaultSize):
    style=wx.DEFAULT_FRAME_STYLE
    if FRAME_NO_TASKBAR==True:
      style|=wx.FRAME_NO_TASKBAR
    wx.Frame.__init__(self, None, wx.ID_ANY, "Bandbreitenmonitor v2.01", pos=pos, size=size, style=style)
    self.panel=Bwm2Panel(self)





# ###########################################################
# Der Starter
if __name__=='__main__':
  fc=wx.FileConfig(localFilename=cfgFile_g)
  spx=fc.ReadInt("pos_x", -1)
  spy=fc.ReadInt("pos_y", -1)
  ssx=fc.ReadInt("size_x", -1)
  ssy=fc.ReadInt("size_y", -1)
  
  sp=(spx, spy) # (-1, -1) entspricht wx.DefaultPosition
  ss=(ssx, ssy) # (-1, -1) entspricht wx.DefaultSize

  app=wx.App(False)
  frame=Bwm2Frame(None, pos=sp, size=ss)
  frame.Show(True)
  app.MainLoop()

