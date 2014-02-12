#!/usr/bin/python2
# -*- coding: utf-8 -*-
from PyQt4 import QtCore,QtGui
from sc_ui import Ui_MainWindow
import os,subprocess,shlex,codecs,re,datetime
from res_rc import *


class ConvertThread(QtCore.QThread):
    """Thread for doing acutal convertion"""
    
    #defining signals
    blockUi=QtCore.pyqtSignal(int)
    makeProgress=QtCore.pyqtSignal()
    fillTable=QtCore.pyqtSignal(int,str)
    done=QtCore.pyqtSignal()
    makeSmallProgress=QtCore.pyqtSignal(int,int)
    prepSmallProgress=QtCore.pyqtSignal(int)
    fileExists=QtCore.pyqtSignal(str)
    
    def __init__(self,parent):
        """Init function; reading AV options from main thread and compiling RE"""
        QtCore.QThread.__init__(self,parent)
        self.parent=parent
        self.ui=parent.ui
        self.audioOptions=parent.audioOptions
        self.audioFormats=parent.audioFormats
        self.videoFormats=parent.videoFormats
        self.videoOptions=parent.videoOptions
        self.reg=re.compile("Duration: ([0-9][0-9]):([0-9][0-9]):([0-9][0-9])")
        self.reg2=re.compile("time=([0-9][0-9]):([0-9][0-9]):([0-9][0-9])")
        
    def getSecs(self,rd):
        """converts hours,minutes and seconds to seconds"""
        return int(rd[2])+int(rd[1])*60+int(rd[0])*3600
        
    def checkQuality(self):
        """checking and adjusting quality"""
        aqindex=self.ui.comboBox_2.currentIndex()
        if aqindex==0:
            ab=320
            vb=8000
        elif aqindex==1:
            ab=254
            vb=4000
        else:
            ab=128
            vb=500
        return ab,vb
        
    def getDuration(self,prc):
        """Getting overall file duration from ffmpeg output"""

        s=""
        conv=False
        self.fullOut=""
        while not conv:
            out=prc.stderr.read(300)
            s+=out
            self.fullOut+=out

            try:
                rd=self.reg.search(s).groups()
                duration=self.getSecs(rd)
                conv=True
            except:
                if prc.poll() is not None:
                    duration=abs(prc.poll())
                    conv=True
        return duration
    
    def getProgress(self,prc,duration,c,i):
        """getting current time value from ffmpeg output"""
        a=""
        
        conv=True
        while conv:
            try:
                a+=prc.stderr.read(60).rstrip()
                if a.strip()!="":
                    rd=self.reg2.search(a).groups()
                    curtime=self.getSecs(rd)
                    self.makeSmallProgress.emit(curtime,c)
                    self.fullOut+=a
                    a=""
                else:
                    raise Exception
            except:
                if prc.poll() is not None:
                    self.makeSmallProgress.emit(duration,c)
                    if int(prc.returncode==0):
                        return True
                    else:
                        return False
                    conv=False
                    
    def genNewName(self,outfp,outext):
        """generating new name if file already exists"""
        try:
            b,sint,_=outfp.rsplit(".",2)
            sint=str(int(sint)+1)
            outfp=".".join([b,sint,outext])
            if os.path.isfile(outfp):
                outfp= self.genNewName(outfp, outext)
        except:
            outfp=outfp.rstrip("."+outext)+".0."+outext
            if os.path.isfile(outfp):
                outfp= self.genNewName(outfp,outext)
        return outfp
        
    def dumpError(self,cmd):
        header="\n\n\n===============================================================================================\
        \nsavc failed to convert file with command:\n"+cmd+"\non "+datetime.datetime.now().strftime("%Y-%m-%d at %H:%M:%s\n\n")
        f=codecs.open("error.log",'a','utf-8')
        f.write(header)            
        f.write(self.fullOut)
        f.close()
        print self.fullOut
    
    
    def run(self):
        """main function - starting thread"""
        self.resp=None
        self.convertFiles=self.parent.convertFiles

        currtext=self.ui.comboBox.currentText()
        if currtext !="":
            outext=str(currtext.split(" > ")[1])
            ab,vb=self.checkQuality()
            self.blockUi.emit(1)
            sdir=self.parent.dir
            c=0
            for i in self.convertFiles:
                orgext=i.rsplit(".",1)[1]
                outfile=i.rsplit(".",1)[0]+"."+outext
                outfp=sdir+os.sep+outfile
                if os.path.isfile(outfp):
                    
                    if self.resp is None:self.fileExists.emit(outfile)
                    while self.resp is None:
                        pass
                    
                    a,b=self.resp
                    if b==0:
                        self.resp=None
                            
                    if a==1:
                        self.fillTable.emit(c,self.tr("Skipped"))
                        self.makeProgress.emit()
                        c+=1
                        continue
                    elif a==2:
                        outfp=self.genNewName(outfp, outext)
                    
                            
                if orgext in self.audioFormats:
                    if outext in self.audioOptions:
                        cmd="ffmpeg -i '"+sdir+os.sep+i+"' -y -ab "+str(ab)+"k "+self.audioOptions[outext]+" '"+outfp+"'"
                    else:
                        cmd="ffmpeg -i '"+sdir+os.sep+i+"' -y -ab "+str(ab)+"k '"+outfp+"'"
                elif orgext in self.videoFormats:
                    if orgext in self.videoOptions:
                        cmd="ffmpeg -i '"+sdir+os.sep+i+"' -y "+str(vb)+"k "+self.videoOptions[orgext]+" -ab "+str(ab)+"k '"+outfp+"'"
                    else:                       
                        cmd="ffmpeg -i '"+sdir+os.sep+i+"' -y -c:v mpeg4 -b:v "+str(vb)+"k -c:a libmp3lame -ab "+str(ab)+"k '"+outfp+"'"
                
                self.fillTable.emit(c,self.tr("Converting..."))
                prc= subprocess.Popen(shlex.split(str(cmd)),stdout=subprocess.PIPE,stderr=subprocess.PIPE)
                #prc.wait()
                #time.sleep(1)
                duration=self.getDuration(prc)
                self.prepSmallProgress.emit(duration)
                
                if self.getProgress(prc,duration,c,i):
                    if self.ui.checkBox.isChecked():
                        os.remove(sdir+os.sep+i)
                    self.fillTable.emit(c,self.tr("Done!"))
                else:
                    
                    self.dumpError(cmd)
                    self.fillTable.emit(c,self.tr("Error!"))

                
                self.makeProgress.emit()
                c+=1
                
                
            self.blockUi.emit(0)
            self.done.emit()
            
            

        
class SCWindow(QtGui.QMainWindow):
    def __init__(self,parent=None):
        QtGui.QWidget.__init__(self,parent)
        self.ui=Ui_MainWindow()
        self.ui.setupUi(self)
        self.ui.fprog.hide()
        self.ui.tprog.hide()
        self.ui.progressBar.setFormat("%v/%m")
        
        
        
        
        self.show()
        
        #self.convertMethods={"mpc":["mp3","ogg"],"wav":["mp3","ogg"],"flac":["mp3","ogg"],"m4a":["mp3","ogg"],"mkv":["avi",],"rmvb":["avi",]}
        self.convertMethods={}
        self.audioFormats=["mp3","ogg","wav","flac","m4a","mpc"]
        for i in self.audioFormats:
            self.convertMethods[i]=list(self.audioFormats)
            self.convertMethods[i].remove(i)
            try:
                self.convertMethods[i].remove("mpc")
            except:
                pass
        
        
        self.videoFormats=["avi","mp4","rmvb","mkv"]
        for i in self.videoFormats:
            self.convertMethods[i]=list(self.videoFormats)
            self.convertMethods[i].remove(i)
           
           
        #this is for output format!
        self.audioOptions={"ogg":"-acodec libvorbis -vn -ac 2"}
        
        #this is for INPUT format!
        self.videoOptions={"rmvb":"-vcodec msmpeg4 -qscale 5 -acodec libmp3lame -ac 2"}
        
        self.ct=ConvertThread(self)

        self.ct.blockUi.connect(self.blockUi)
        self.ct.makeProgress.connect(self.makeProgess)
        self.ct.fillTable.connect(self.fillTable)
        self.ct.done.connect(self.setDone)
        self.ct.prepSmallProgress.connect(self.prepSmallProgress)
        self.ct.makeSmallProgress.connect(self.makeSmallProgress)
        self.ct.fileExists.connect(self.fileExists)
        
        
        self.ui.buttonBox.buttons()[0].setText(self.tr("Convert"))
        self.ui.buttonBox.buttons()[0].setDisabled(True)


        
        self.ui.pushButton.clicked.connect(self.selectDir)
        self.ui.pushButton_2.clicked.connect(self.selectFiles)
        self.ui.comboBox.currentIndexChanged.connect(self.conversionSelected)

        self.ui.buttonBox.accepted.connect(self.startConverting)
        self.ui.buttonBox.rejected.connect(self.quit)
        self.ui.actionQuit.triggered.connect(self.quit)
        self.ui.actionAbout.triggered.connect(self.about)
        
        self.ui.tableWidget.setColumnWidth(0,550)
        self.ui.tableWidget.setColumnWidth(1,200)

        
    
    def selectDir(self):
        a=QtGui.QFileDialog()
        a.setFileMode(a.Directory)
        res=a.exec_()
        if res:
            self.ui.progressBar.setValue(0)
            self.filesRemoved=False
            self.files={}
            self.dir=a.selectedFiles()[0]
            self.ui.lineEdit.setText(unicode(self.dir))
            fileslist=os.listdir(unicode(self.dir))
            fileslist.sort()
            for i in fileslist:
                try:
                    ext=unicode(i).rsplit(".",1)[1]
                except:
                    continue
                if ext in self.convertMethods:
                    if ext in self.files:
                        self.files[ext].append(i)
                    else:
                        self.files[ext]=[i,]
                        
            if len(self.files):
                self.done=False
                
                self.fillConvertMethods(self.files)
            else:
                QtGui.QMessageBox.warning(self,self.tr("Error!"),self.tr("In selected directory there are no supported files"))
    
    def selectFiles(self):
        a=QtGui.QFileDialog()
        audiofilters="*."+" *.".join(self.audioFormats)
        videofilters="*."+" *.".join(self.videoFormats)
        a.setFileMode(a.ExistingFiles)
        a.setNameFilters([self.tr("Supported audio formats (")+audiofilters+")", self.tr("Supported video formats (")   +videofilters+")"])
        res=a.exec_()
        if res:
            self.ui.progressBar.setValue(0)
            self.filesRemoved=False
            self.files={}
            for i in a.selectedFiles(): 
                self.dir,fname=str(i).rsplit(os.sep,1)
                ext=fname.rsplit(".",1)[1]
                if ext in self.files:
                    self.files[ext].append(fname)
                else:
                    self.files[ext]=[fname,]
            if len(self.files):
                self.done=False
                self.fillConvertMethods(self.files)
                self.ui.comboBox.setCurrentIndex(1)
    
    def fillConvertMethods(self,files):
        self.ui.tprog.hide()
        self.ui.fprog.hide()
        self.ui.comboBox.clear()
        
        convertMethods=[]
        audio=False
        video=False
        for i in files:
            for j in self.convertMethods[i]:
                convertMethods.append(i+" > "+j)
            if i in self.audioFormats:audio=True
            if i in self.videoFormats:video=True 
                
        self.ui.comboBox.addItem("")
        if audio and len(files)>1:
            for i in self.audioFormats:
                if i not in files and i!="mpc":
                    self.ui.comboBox.addItem("*audio > "+i) 

        if video and len(files)>1:
            for i in self.videoFormats:
                if i not in files:
                    self.ui.comboBox.addItem("*video > "+i) 
            
            
        for i in convertMethods:
            self.ui.comboBox.addItem(i)
            
    def conversionSelected(self):
        self.ui.tprog.hide()
        self.ui.fprog.hide()
        currtext=self.ui.comboBox.currentText()
        self.ui.tableWidget.clear()
        
        self.done=False
        if not self.filesRemoved:
            self.ui.buttonBox.buttons()[0].setText(self.tr("Convert"))
        if currtext !="":
            self.ui.progressBar.setValue(0)

            ext=str(currtext.split(" > ")[0])
            c=0
            files=[]
            self.ext=ext
            if ext.startswith("*audio"):
                for i in self.audioFormats:
                    if i in self.files: files+=self.files[i]
            elif ext.startswith("*wideo"):
                for i in self.videoFormats:
                    if i in self.files: files+=self.files[i]
            else:                
                files=self.files[ext]
            self.ui.tableWidget.setRowCount(len(files))
            for i in files:
                self.ui.tableWidget.setItem(c,0,QtGui.QTableWidgetItem(i))
                c+=1
            if len(files)>0:
                self.ui.progressBar.setMaximum(len(files))
            self.convertFiles=files

            self.ui.buttonBox.buttons()[0].setDisabled(False)
        else:
            self.ui.buttonBox.buttons()[0].setDisabled(True)
   
    def blockUi(self,i):
        self.setDisabled(i)
        
    def prepSmallProgress(self,i):
        self.ui.progressBar_2.setMaximum(i)
        self.ui.progressBar_2.setValue(0)

        self.ui.fprog.show()
        
    def makeSmallProgress(self,i,c):
        item=  self.ui.tableWidget.item(c, 0)   
        self.ui.tableWidget.scrollToItem(item)
        self.ui.progressBar_2.setValue(i)
        self.ui.progressBar_2.setFormat(item.text()+ " - %p%")


    def makeProgess(self):
        self.ui.progressBar.setValue(self.ui.progressBar.value()+1)
        
    def fillTable(self,c,ttext):
        self.ui.tableWidget.setItem(c,1,QtGui.QTableWidgetItem(unicode(ttext)))

    def startConverting(self):
        if self.done:
            self.quit()
        else:
            self.ct.start()
            if len(self.convertFiles)>1:
                self.ui.tprog.show()
            else:
                self.ui.tprog.hide()
    def setDone(self):
        self.done=True
        self.ui.buttonBox.buttons()[0].setText(u"Wyjdź")
        if self.ui.checkBox.isChecked():
            self.filesRemoved=True
            for i in self.convertFiles:
                ext=i.rsplit(".",1)[1]
                self.files[ext].remove(i)
                
    def fileExists(self,fname):
        msg=QtGui.QMessageBox(self)
        msg.setWindowTitle(self.tr("File exists"))
        msg.setText(str(self.tr("Output file %s already exists!"))%fname)
        obtn=QtGui.QPushButton(self.tr("Overwrite"))
        sbtn=QtGui.QPushButton(self.tr("Skip"))
        rbtn=QtGui.QPushButton(self.tr("Automatically rename"))
        chckbox=QtGui.QCheckBox(self.tr("Remember selection"))
        

        chckbox.blockSignals(True)
        msg.addButton(obtn,msg.AcceptRole)
        msg.addButton(sbtn,msg.RejectRole)
        msg.addButton(rbtn,msg.RejectRole)
        msg.addButton(chckbox,msg.ActionRole)

        resp=msg.exec_()
        if chckbox.isChecked():rmmbr=1
        else:rmmbr=0
        self.ct.resp=resp,rmmbr
    
    def quit(self):
        sys.exit()

    def about(self):
        a=self.tr("Simple AV converter<br>This application suppose to \
        be the simplest way to convert audio and video files. \
        There are no advanced options - just select file, select \
        format, quality and go!<br><br>Jakub Wrożyna middleofdreams@gmail.com")
        QtGui.QMessageBox.information(self, "About", a)

if __name__=="__main__":
    import sys
    app=QtGui.QApplication(sys.argv)
    locale = QtCore.QLocale.system().name()
    qtTranslator = QtCore.QTranslator()

    if qtTranslator.load("savc_" + locale, ":tr/"):
        app.installTranslator(qtTranslator)
    myapp=SCWindow()
    app.exec_()