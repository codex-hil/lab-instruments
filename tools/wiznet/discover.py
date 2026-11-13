import socket,time,json
s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM);s.setsockopt(socket.SOL_SOCKET,socket.SO_BROADCAST,1);s.bind(('',50001));s.settimeout(.5)
cmds=['MC','MN','VR','LI','IM','SM','GW','OP','QO','LP','QL','BR','EB','DB','ED','PR','EP','SB','ES','FL','EF']
s.sendto(b'MA'+b'\xff'*6+b'\r\nPW \r\n'+''.join(c+'\r\n' for c in cmds).encode(),('255.255.255.255',50001))
end=time.monotonic()+3;out=[]
while time.monotonic()<end:
 try:data,peer=s.recvfrom(8192)
 except socket.timeout:continue
 if peer[0]=='192.168.2.107':continue
 values={}
 for line in data.split(b'\r\n'):
  if len(line)<2:continue
  key=line[:2].decode('ascii',errors='replace')
  if key=='PW':continue
  values[key]=line[2:].hex(':') if key == 'MA' else line[2:].decode('ascii',errors='replace')
 out.append({'peer':peer[0],'values':values})
print(json.dumps(out,indent=2))
