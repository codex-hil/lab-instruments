var views=[['phase','p'],['oadev','a'],['mdev','m'],['ohdev','h'],['tdev','t'],['mtie','M']];
var index=0;
function EventRunScript() {
 FileCloseAllPlots();FileLoad(ScriptStrParam(0),ScriptStrParam(1));
 DisplaySelectPlot(0);ScriptBindToPlot(0);
 TraceXDEVBars(false);TraceXDEVClipBW(false);TraceXDEVClipConfidence(false);TraceXDEVSpline(false);
 TracePhaseFreqResid(false);TracePhaseFreqTrend(false);TracePhaseFreqZero(false);TracePhaseZero(false);
 ScriptSetWindowPos('0x0, 1, (-1,-1), (-1,-1), (10,10,1410,970)');
 MeasurementSelectView(views[0][1]);DisplayRefresh();TimeSetTimer(ScriptStrParam(3)==='png'?1000:250);
}
function EventTimer() {
 FileExportASCIIData(',',ScriptStrParam(2),views[index][0]+'.csv');
 if(ScriptStrParam(3)==='png')FileSave(ScriptStrParam(2),views[index][0]+'.png');
 index++;
 if(index<views.length){MeasurementSelectView(views[index][1]);DisplayRefresh();return;}
 TimeSetTimer(0);FileSave(ScriptStrParam(2),'roundtrip.tim');
 FileSaveText(ScriptStrParam(2),'completed.json','{"completed":true,"views":6}');
 FileExitApplication(0);ScriptEnd();
}
