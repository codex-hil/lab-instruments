'********************************************************************************************
'*                                                                                          *
'*  Check the status of the unit by using ":STATUS?" every 1 second.                        *
'*                                                                                          *
'********************************************************************************************
Imports System
Imports System.Text
Imports System.IO
Imports System.Net
Imports System.Net.Sockets
Imports System.Threading
Imports Microsoft.VisualBasic


Public Class Form1
    Inherits System.Windows.Forms.Form

#Region "Windows form designer create."

    Public Sub New()
        MyBase.New()

        InitializeComponent()


        BTN_DIS_CONNECT.Enabled() = False
    End Sub

    Protected Overloads Overrides Sub Dispose(ByVal disposing As Boolean)
        If disposing Then
            If Not (components Is Nothing) Then
                components.Dispose()
            End If
        End If
        MyBase.Dispose(disposing)
    End Sub

    Private components As System.ComponentModel.IContainer

    Friend WithEvents LBL_IP_ADDRESS As System.Windows.Forms.Label
    Friend WithEvents LBL_PORT As System.Windows.Forms.Label
    Friend WithEvents TXT_BOX_IP As System.Windows.Forms.TextBox
    Friend WithEvents TXT_BOX_PORT As System.Windows.Forms.TextBox
    Friend WithEvents LBL_STATUS As System.Windows.Forms.Label
    Friend WithEvents BTN_CONNECT As System.Windows.Forms.Button
    Friend WithEvents BTN_DIS_CONNECT As System.Windows.Forms.Button
    Friend WithEvents TXT_BOX_RECEIVE As System.Windows.Forms.TextBox
    Friend WithEvents LBL_STS As System.Windows.Forms.Label
    Friend WithEvents BTN_EXEC As System.Windows.Forms.Button
    Friend WithEvents Timer As System.Windows.Forms.Timer
    Friend WithEvents BTN_STOP As System.Windows.Forms.Button
    <System.Diagnostics.DebuggerStepThrough()> Private Sub InitializeComponent()
        Me.components = New System.ComponentModel.Container()
        Me.LBL_IP_ADDRESS = New System.Windows.Forms.Label()
        Me.LBL_PORT = New System.Windows.Forms.Label()
        Me.TXT_BOX_IP = New System.Windows.Forms.TextBox()
        Me.TXT_BOX_PORT = New System.Windows.Forms.TextBox()
        Me.LBL_STATUS = New System.Windows.Forms.Label()
        Me.BTN_CONNECT = New System.Windows.Forms.Button()
        Me.BTN_DIS_CONNECT = New System.Windows.Forms.Button()
        Me.BTN_EXEC = New System.Windows.Forms.Button()
        Me.TXT_BOX_RECEIVE = New System.Windows.Forms.TextBox()
        Me.LBL_STS = New System.Windows.Forms.Label()
        Me.Timer = New System.Windows.Forms.Timer(Me.components)
        Me.BTN_STOP = New System.Windows.Forms.Button()
        Me.SuspendLayout()
        '
        'LBL_IP_ADDRESS
        '
        Me.LBL_IP_ADDRESS.Location = New System.Drawing.Point(8, 8)
        Me.LBL_IP_ADDRESS.Name = "LBL_IP_ADDRESS"
        Me.LBL_IP_ADDRESS.Size = New System.Drawing.Size(64, 16)
        Me.LBL_IP_ADDRESS.TabIndex = 1
        Me.LBL_IP_ADDRESS.Text = "IP address"
        '
        'LBL_PORT
        '
        Me.LBL_PORT.Location = New System.Drawing.Point(8, 32)
        Me.LBL_PORT.Name = "LBL_PORT"
        Me.LBL_PORT.Size = New System.Drawing.Size(64, 16)
        Me.LBL_PORT.TabIndex = 1
        Me.LBL_PORT.Text = "Port"
        '
        'TXT_BOX_IP
        '
        Me.TXT_BOX_IP.Location = New System.Drawing.Point(88, 8)
        Me.TXT_BOX_IP.Name = "TXT_BOX_IP"
        Me.TXT_BOX_IP.Size = New System.Drawing.Size(152, 19)
        Me.TXT_BOX_IP.TabIndex = 2
        Me.TXT_BOX_IP.Text = "192.168.1.240"
        '
        'TXT_BOX_PORT
        '
        Me.TXT_BOX_PORT.Location = New System.Drawing.Point(88, 29)
        Me.TXT_BOX_PORT.Name = "TXT_BOX_PORT"
        Me.TXT_BOX_PORT.Size = New System.Drawing.Size(152, 19)
        Me.TXT_BOX_PORT.TabIndex = 2
        Me.TXT_BOX_PORT.Text = "8802"
        '
        'LBL_STATUS
        '
        Me.LBL_STATUS.Location = New System.Drawing.Point(88, 56)
        Me.LBL_STATUS.Name = "LBL_STATUS"
        Me.LBL_STATUS.Size = New System.Drawing.Size(152, 19)
        Me.LBL_STATUS.TabIndex = 3
        Me.LBL_STATUS.Text = "Disconnect"
        '
        'BTN_CONNECT
        '
        Me.BTN_CONNECT.Location = New System.Drawing.Point(8, 88)
        Me.BTN_CONNECT.Name = "BTN_CONNECT"
        Me.BTN_CONNECT.Size = New System.Drawing.Size(112, 24)
        Me.BTN_CONNECT.TabIndex = 4
        Me.BTN_CONNECT.Text = "Connect"
        '
        'BTN_DIS_CONNECT
        '
        Me.BTN_DIS_CONNECT.Location = New System.Drawing.Point(128, 88)
        Me.BTN_DIS_CONNECT.Name = "BTN_DIS_CONNECT"
        Me.BTN_DIS_CONNECT.Size = New System.Drawing.Size(112, 24)
        Me.BTN_DIS_CONNECT.TabIndex = 4
        Me.BTN_DIS_CONNECT.Text = "Disconnect"
        '
        'BTN_EXEC
        '
        Me.BTN_EXEC.Enabled = False
        Me.BTN_EXEC.Location = New System.Drawing.Point(8, 120)
        Me.BTN_EXEC.Name = "BTN_EXEC"
        Me.BTN_EXEC.Size = New System.Drawing.Size(112, 24)
        Me.BTN_EXEC.TabIndex = 4
        Me.BTN_EXEC.Text = "Execute"
        '
        'TXT_BOX_RECEIVE
        '
        Me.TXT_BOX_RECEIVE.Location = New System.Drawing.Point(8, 152)
        Me.TXT_BOX_RECEIVE.Multiline = True
        Me.TXT_BOX_RECEIVE.Name = "TXT_BOX_RECEIVE"
        Me.TXT_BOX_RECEIVE.ScrollBars = System.Windows.Forms.ScrollBars.Vertical
        Me.TXT_BOX_RECEIVE.Size = New System.Drawing.Size(232, 120)
        Me.TXT_BOX_RECEIVE.TabIndex = 6
        '
        'LBL_STS
        '
        Me.LBL_STS.Location = New System.Drawing.Point(8, 56)
        Me.LBL_STS.Name = "LBL_STS"
        Me.LBL_STS.Size = New System.Drawing.Size(64, 16)
        Me.LBL_STS.TabIndex = 1
        Me.LBL_STS.Text = "Status"
        '
        'Timer
        '
        '
        'BTN_STOP
        '
        Me.BTN_STOP.Enabled = False
        Me.BTN_STOP.Location = New System.Drawing.Point(128, 120)
        Me.BTN_STOP.Name = "BTN_STOP"
        Me.BTN_STOP.Size = New System.Drawing.Size(112, 24)
        Me.BTN_STOP.TabIndex = 4
        Me.BTN_STOP.Text = "Stop"
        '
        'Form1
        '
        Me.AutoScaleBaseSize = New System.Drawing.Size(5, 12)
        Me.ClientSize = New System.Drawing.Size(248, 277)
        Me.Controls.Add(Me.LBL_STS)
        Me.Controls.Add(Me.TXT_BOX_RECEIVE)
        Me.Controls.Add(Me.BTN_CONNECT)
        Me.Controls.Add(Me.LBL_STATUS)
        Me.Controls.Add(Me.TXT_BOX_IP)
        Me.Controls.Add(Me.LBL_IP_ADDRESS)
        Me.Controls.Add(Me.LBL_PORT)
        Me.Controls.Add(Me.TXT_BOX_PORT)
        Me.Controls.Add(Me.BTN_DIS_CONNECT)
        Me.Controls.Add(Me.BTN_EXEC)
        Me.Controls.Add(Me.BTN_STOP)
        Me.MaximizeBox = False
        Me.MinimizeBox = False
        Me.Name = "Form1"
        Me.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        Me.Text = "Form1"
        Me.ResumeLayout(False)
        Me.PerformLayout()

    End Sub

#End Region
    '****************************************************************
    '*  Connect                                                    *
    '****************************************************************
    Dim g_TcpClient As TcpClient

    Private Sub BTN_CONNECT_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_CONNECT.Click
        If (TXT_BOX_IP.Text = "") Then
            Exit Sub
        End If

        If (TXT_BOX_PORT.Text = "") Then
            Exit Sub
        End If

        LBL_STATUS.Text = "Waiting..."
        g_TcpClient = New System.Net.Sockets.TcpClient(TXT_BOX_IP.Text, Val(TXT_BOX_PORT.Text))
        LBL_STATUS.Text = "Connect"
        TXT_BOX_IP.Enabled() = False
        TXT_BOX_PORT.Enabled() = False
        BTN_CONNECT.Enabled() = False
        BTN_DIS_CONNECT.Enabled() = True
        BTN_EXEC.Enabled() = True
    End Sub


    '****************************************************************
    '*  Disconnect                                                  *
    '****************************************************************
    Private Sub BTN_DIS_CONNECT_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_DIS_CONNECT.Click
        Timer.Enabled() = False
        BTN_EXEC.Enabled() = True
        BTN_STOP.Enabled() = False
        g_TcpClient.Close()
        LBL_STATUS.Text = "Disconnect"
        TXT_BOX_IP.Enabled() = True
        TXT_BOX_PORT.Enabled() = True
        BTN_CONNECT.Enabled() = True
        BTN_DIS_CONNECT.Enabled() = False
        BTN_EXEC.Enabled() = False
    End Sub


    '****************************************************************
    '*  Transmit the data                                           *
    '****************************************************************
    Private Sub SendMsg(ByRef strMsg As String)
        Try
            strMsg = strMsg & vbCrLf
            Dim bytesWrite As [Byte]() = Encoding.ASCII.GetBytes(strMsg)
            g_TcpClient.GetStream().Write(bytesWrite, 0, bytesWrite.Length)
        Catch ex As Exception
            MessageBox.Show(ex.ToString(), "Error", MessageBoxButtons.OK, MessageBoxIcon.Exclamation)
        End Try
    End Sub

    '****************************************************************
    '*  Transmit and recieve the data                               *
    '****************************************************************
    Dim MsgBuf As String

    Private Sub QueryMsg(ByRef strMsg As String)
        Dim buf As String
        buf = LBL_STATUS.Text
        LBL_STATUS.Text = "Reciving..."
        SendMsg(strMsg)
        ReciveMsg()
        LBL_STATUS.Text = buf
    End Sub


    '****************************************************************
    '*  Recieve the data.                                           *
    '****************************************************************
    Private Sub ReciveMsg()
        MsgBuf = Nothing
        Dim ASCII As Encoding = Encoding.ASCII
        Dim RecvBytes(255) As [Byte]
        Dim bytes As Int32 = g_TcpClient.GetStream().Read(RecvBytes, 0, RecvBytes.Length)
        MsgBuf = ASCII.GetString(RecvBytes, 0, bytes)
    End Sub


    '****************************************************************
    '*  Execute                                                     *
    '****************************************************************
    Dim MAX_UNIT_NUM As Integer
    Dim intUnit(8) As Integer

    Private Sub BTN_EXEC_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_EXEC.Click
        BTN_EXEC.Enabled() = False
        BTN_STOP.Enabled() = True
        TXT_BOX_RECEIVE.Text = ""

        SendMsg(":HEADER OFF")

        Timer.Interval() = 1000
        Timer.Enabled() = True

    End Sub

    '****************************************************************
    '* Check the data regularly                                     *
    '****************************************************************
    Private Sub Timer_Tick(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Timer.Tick
        Dim data As Integer

        TXT_BOX_RECEIVE.Text = ""

        QueryMsg(":STATUS?")
        data = Val(MsgBuf)

        If (data = 0) Then
            TXT_BOX_RECEIVE.SelectedText = "stopping" & vbCrLf
        End If

        If ((data And &H1) <> 0) Then
            TXT_BOX_RECEIVE.SelectedText = "starting" & vbCrLf
        End If

        If ((data And &H2) <> 0) Then
            TXT_BOX_RECEIVE.SelectedText = "storing" & vbCrLf
        End If

        If ((data And &H4) <> 0) Then
            TXT_BOX_RECEIVE.SelectedText = "awaiting trigger" & vbCrLf
        End If

        If ((data And &H8) <> 0) Then
            TXT_BOX_RECEIVE.SelectedText = "pre-trigger wait period" & vbCrLf
        End If

        If ((data And &H10) <> 0) Then
            TXT_BOX_RECEIVE.SelectedText = "acquiring a waveform" & vbCrLf
        End If

        If ((data And &H20) <> 0) Then
            TXT_BOX_RECEIVE.SelectedText = "saving" & vbCrLf
        End If
    End Sub


    '****************************************************************
    '*  Stop                                                        *
    '****************************************************************
    Private Sub BTN_STOP_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_STOP.Click
        Timer.Enabled() = False
        BTN_EXEC.Enabled() = True
        BTN_STOP.Enabled() = False
    End Sub

    Private Sub TXT_BOX_IP_TextChanged(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles TXT_BOX_IP.TextChanged

    End Sub
End Class
