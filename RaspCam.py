#!/usr/bin/python
# -*- coding: utf8 -*-

import os.path
import shutil
import time
import picamera
import cv2
import numpy
import smtplib

from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart

# Configuration
import Config

bContinue = True

# Capture d'une photo avec la caméra
def CapturePhoto(aPhoto):
   try:
      if os.path.isfile(aPhoto):
         os.remove(aPhoto)
      with picamera.PiCamera() as camera:
         camera.resolution = (Config.PhotoWidth, Config.PhotoHeight)
         camera.start_preview()
         # Camera warm-up time
         time.sleep(1)
         camera.capture(aPhoto, resize=(Config.PhotoWidth, Config.PhotoHeight))
   except picamera.PiCameraRuntimeError:
      return True
   except:
      return False

# Détection d'un mouvement entre 2 images
def DetectionMouvement():
   # - Construction des images en niveau de gris
   ImgT1 = cv2.imread(Config.RepertoirePhotosTmp + Config.PhotoT1)
   ImgT1Gray = cv2.cvtColor(ImgT1, cv2.COLOR_BGR2GRAY)
   ImgT2 = cv2.imread(Config.RepertoirePhotosTmp + Config.PhotoT2)
   ImgT2Gray = cv2.cvtColor(ImgT2, cv2.COLOR_BGR2GRAY)
   # - Construction des images de différences
   ImgDiff21 = cv2.absdiff(ImgT2Gray, ImgT1Gray)
   # - Construction des filtres [3x3]
   Kernel = numpy.ones((3,3), numpy.float32)/25
   Kernel2 = numpy.ones((3,3),numpy.uint8)
   # - Construction des images filtrées
   ImgDiffFilter = cv2.filter2D(ImgDiff21, -1, Kernel)
   ImgDiffFilterOpening = cv2.morphologyEx(ImgDiffFilter, cv2.MORPH_OPEN, Kernel2)
   ImgDiffFilterClosing = cv2.morphologyEx(ImgDiffFilterOpening, cv2.MORPH_CLOSE, Kernel2)
   ret, ImgDiffFilterFinal = cv2.threshold(ImgDiffFilterClosing,10,255,cv2.THRESH_BINARY)
   # - Calcul du nombre pixel "Non Zéro"
   NbPixNonZero = cv2.countNonZero(ImgDiffFilterFinal)
   PourcentageNonZero = (float(NbPixNonZero) / (Config.PhotoHeight * Config.PhotoWidth)) * 100
   # - Détection du mouvement basé sur le nombre de pixels non noir
   if PourcentageNonZero > Config.SeuilMouvement:
      cv2.putText(ImgDiffFilterFinal, str(PourcentageNonZero), (0, 480), cv2.FONT_HERSHEY_PLAIN, 1.5, (255), thickness=2)
      cv2.imwrite(Config.RepertoirePhotosTmp + Config.PhotoTDiff, ImgDiffFilterFinal)
      return True
   else:
      return False

def EnregistrementImages(aDate, aHeureMinuteSeconde):
   RepertoireDate = aDate + "/"
   RepertoireHeure = time.strftime("%H", time.localtime()) + "/"
   NomImage = aDate + "_" + aHeureMinuteSeconde
   
   # Création du répertoire à la date du jour s'il n'existe pas
   if not os.path.isdir(Config.RepertoirePhotos + RepertoireDate):
      os.mkdir(Config.RepertoirePhotos + RepertoireDate)
   # Création du répertoire de l'heure courante
   if not os.path.isdir(Config.RepertoirePhotos + RepertoireDate + RepertoireHeure):
      os.mkdir(Config.RepertoirePhotos + RepertoireDate + RepertoireHeure)
   # Sauvegarde des photos
   shutil.copy(Config.RepertoirePhotosTmp + Config.PhotoT1, Config.RepertoirePhotos + RepertoireDate + RepertoireHeure + NomImage + "_" + Config.PhotoT1)
   shutil.copy(Config.RepertoirePhotosTmp + Config.PhotoT2, Config.RepertoirePhotos + RepertoireDate + RepertoireHeure + NomImage + "_" + Config.PhotoT2)
   shutil.copy(Config.RepertoirePhotosTmp + Config.PhotoTDiff, Config.RepertoirePhotos + RepertoireDate + RepertoireHeure + NomImage + "_" + Config.PhotoTDiff)

# Envoi du mail contenant les images
def EnvoiMail(aDate, aHeureMinuteSeconde):
   msg = MIMEMultipart()
   msg['Subject'] = 'Mouvement détecté ' + aDate + ' à ' + aHeureMinuteSeconde
   msg['From'] = Config.MailOrig
   msg['To'] = Config.MailDest
   # Photo 1
   fp1 = open(Config.RepertoirePhotosTmp + Config.PhotoT1, 'rb')
   img1 = MIMEImage(fp1.read())
   fp1.close()
   msg.attach(img1)
   # Photo 2
   fp2 = open(Config.RepertoirePhotosTmp + Config.PhotoT2, 'rb')
   img2 = MIMEImage(fp2.read())
   fp2.close()
   msg.attach(img2)
   # Photo Diff
   fpDiff = open(Config.RepertoirePhotosTmp + Config.PhotoTDiff, 'rb')
   imgDiff = MIMEImage(fpDiff.read())
   fpDiff.close()
   msg.attach(imgDiff)
   # Envoi
   username = Config.MailOrig
   password = Config.MailPassword
   server = smtplib.SMTP_SSL(Config.MailSMTP)
   server.login(username,password)
   server.sendmail(Config.MailOrig, Config.MailDest, msg.as_string())
   server.quit()

# Main
def main ():
   while bContinue:
      bMouvementDetecte = False
      OldPhoto = Config.RepertoirePhotosTmp + Config.PhotoT1
      NewPhoto = Config.RepertoirePhotosTmp + Config.PhotoT2

      # Mise à jour des photos à traiter
      if os.path.isfile(OldPhoto): 
         os.remove(OldPhoto)
      if os.path.isfile(NewPhoto): 
         shutil.copy(NewPhoto, OldPhoto)
   
      # Prise de la nouvelle photo
      CapturePhoto(NewPhoto)
      shutil.copy(NewPhoto, Config.RepertoireServer + Config.LastPhoto)
   
      # Detection du mouvement
      if os.path.isfile(OldPhoto) and os.path.isfile(NewPhoto):
         bMouvementDetecte = DetectionMouvement()
      
      # Enregistrement en cours et mouvement détecté
      if os.path.isfile(Config.FichierEnregistrementOn) and bMouvementDetecte:
         Date = time.strftime("%Y%m%d", time.localtime())
         HeureMinuteSeconde = time.strftime("%H:%M:%S", time.localtime())
      
         # Sauvegarde des images
         EnregistrementImages (Date, HeureMinuteSeconde)
      
         # Envoi d'un mail
         EnvoiMail(Date, HeureMinuteSeconde)

if __name__ == "__main__":
   main()
