var ticks=0;
function EventRunScript() {
FileLoad("Z:\\home\\timelab\\wr-timing\\evidence", "imported-pps.tim");
DisplaySelectPlot(0);ScriptBindToPlot(0);TimeSetTimer(1000);
}
function EventTimer() {
ticks++;
MeasurementSelectView((ticks%2) ? "a":"t");DisplayRefresh();
if(ticks==1 || ticks==60 || ticks==120) FileSave("Z:\\home\\timelab\\wr-timing\\results", "soak-"+ticks+".png");
if(ticks>=120) {
TimeSetTimer(0);FileSaveText("Z:\\home\\timelab\\wr-timing\\results", "soak-pass.txt", "120 timer callbacks, alternating ADEV and TDEV, completed");
FileExitApplication(0);ScriptEnd();
}
}
