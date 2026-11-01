function EventRunScript() {
FileSaveText("Z:\\home\\timelab\\wr-timing\\results", "smoke.txt", "JS OK params="+ScriptParamCount());
FileSave("Z:\\home\\timelab\\wr-timing\\results", "empty.png");
FileExitApplication(0); ScriptEnd();
}
