var stage=0;
function EventRunScript() {
FileCloseAllPlots();
FileLoad(ScriptStrParam(0),ScriptStrParam(1));
DisplaySelectPlot(0);ScriptBindToPlot(0);
ScriptSetWindowPos("0x0, 1, (-1,-1), (-1,-1), (10,10,1410,970)");
MeasurementSelectView("a");DisplayRefresh();TimeSetTimer(1000);
}
function EventTimer() {
if(stage===0) {
FileExportASCIIData(",",ScriptStrParam(2),"adev.csv");
FileSave(ScriptStrParam(2),"adev.png");
MeasurementSelectView("t");DisplayRefresh();stage=1;return;
}
TimeSetTimer(0);
FileExportASCIIData(",",ScriptStrParam(2),"tdev.csv");
FileSave(ScriptStrParam(2),"tdev.png");
FileSave(ScriptStrParam(2),"roundtrip.tim");
FileExitApplication(0);ScriptEnd();
}
