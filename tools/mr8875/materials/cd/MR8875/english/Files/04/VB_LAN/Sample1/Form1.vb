'****************************************************************************
'*                                                                          *
'*  This program conects to the MEMORY HiCORDR and starts communication.    *
'*                                                                          *
'****************************************************************************
Imports System
Imports System.Text
Imports System.IO
Imports System.Net
Imports System.Net.Sockets
Imports System.Threading
Imports Microsoft.VisualBasic

Public Class Form1
    Inherits System.Windows.Forms.Form

#Region " Windows form designer create."

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
    Friend WithEvents BTN_SEND As System.Windows.Forms.Button
    Friend WithEvents TXT_BOX_COMMAND As System.Windows.Forms.TextBox
    Friend WithEvents TXT_BOX_RECEIVE As System.Windows.Forms.TextBox
    Friend WithEvents LBL_STS As System.Windows.Forms.Label
    <System.Diagnostics.DebuggerStepThrough()> Private Sub InitializeComponent()
        Me.LBL_IP_ADDRESS = New System.Windows.Forms.Label()
        Me.LBL_PORT = New System.Windows.Forms.Label()
        Me.TXT_BOX_IP = New System.Windows.Forms.TextBox()
        Me.TXT_BOX_PORT = New System.Windows.Forms.TextBox()
        Me.LBL_STATUS = New System.Windows.Forms.Label()
        Me.BTN_CONNECT = New System.Windows.Forms.Button()
        Me.BTN_DIS_CONNECT = New System.Windows.Forms.Button()
        Me.BTN_SEND = New System.Windows.Forms.Button()
        Me.TXT_BOX_COMMAND = New System.Windows.Forms.TextBox()
        Me.TXT_BOX_RECEIVE = New System.Windows.Forms.TextBox()
        Me.LBL_STS = New System.Windows.Forms.Label()
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
        'BTN_SEND
        '
        Me.BTN_SEND.Enabled = False
        Me.BTN_SEND.Location = New System.Drawing.Point(8, 120)
        Me.BTN_SEND.Name = "BTN_SEND"
        Me.BTN_SEND.Size = New System.Drawing.Size(80, 24)
        Me.BTN_SEND.TabIndex = 4
        Me.BTN_SEND.Text = "Send"
        '
        'TXT_BOX_COMMAND
        '
        Me.TXT_BOX_COMMAND.Enabled = False
        Me.TXT_BOX_COMMAND.Location = New System.Drawing.Point(96, 125)
        Me.TXT_BOX_COMMAND.Name = "TXT_BOX_COMMAND"
        Me.TXT_BOX_COMMAND.Size = New System.Drawing.Size(144, 19)
        Me.TXT_BOX_COMMAND.TabIndex = 5
        Me.TXT_BOX_COMMAND.Text = "*IDN?"
        '
        'TXT_BOX_RECEIVE
        '
        Me.TXT_BOX_RECEIVE.Enabled = False
        Me.TXT_BOX_RECEIVE.Location = New System.Drawing.Point(8, 152)
        Me.TXT_BOX_RECEIVE.Multiline = True
        Me.TXT_BOX_RECEIVE.Name = "TXT_BOX_RECEIVE"
        Me.TXT_BOX_RECEIVE.ScrollBars = System.Windows.Forms.ScrollBars.Vertical
        Me.TXT_BOX_RECEIVE.Size = New System.Drawing.Size(232, 48)
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
        'Form1
        '
        Me.AutoScaleBaseSize = New System.Drawing.Size(5, 12)
        Me.ClientSize = New System.Drawing.Size(248, 205)
        Me.Controls.Add(Me.LBL_STS)
        Me.Controls.Add(Me.TXT_BOX_RECEIVE)
        Me.Controls.Add(Me.TXT_BOX_COMMAND)
        Me.Controls.Add(Me.BTN_CONNECT)
        Me.Controls.Add(Me.LBL_STATUS)
        Me.Controls.Add(Me.TXT_BOX_IP)
        Me.Controls.Add(Me.LBL_IP_ADDRESS)
        Me.Controls.Add(Me.LBL_PORT)
        Me.Controls.Add(Me.TXT_BOX_PORT)
        Me.Controls.Add(Me.BTN_DIS_CONNECT)
        Me.Controls.Add(Me.BTN_SEND)
        Me.MaximizeBox = False
        Me.MinimizeBox = False
        Me.Name = "Form1"
        Me.StartPosition = System.Windows.Forms.FormStartPosition.CenterScreen
        Me.Text = "Form1"
        Me.ResumeLayout(False)
        Me.PerformLayout()

    End Sub

#End Region

    Dim g_TcpClient As TcpClient
    Dim g_Buffer(256) As Byte
    Dim g_strRcv As String

    '****************************************************************
    '*  Connect                                                     *
    '****************************************************************
    Private Sub BTN_CONNECT_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_CONNECT.Click
        If (TXT_BOX_IP.Text = "") Then
            Exit Sub
        End If

        If (TXT_BOX_PORT.Text = "") Then
            Exit Sub
        End If

        Try
            LBL_STATUS.Text = "Waiting..."
            g_TcpClient = New System.Net.Sockets.TcpClient(TXT_BOX_IP.Text, Val(TXT_BOX_PORT.Text))
            LBL_STATUS.Text = "Connected"
            TXT_BOX_IP.Enabled() = False
            TXT_BOX_PORT.Enabled() = False
            BTN_CONNECT.Enabled() = False
            BTN_DIS_CONNECT.Enabled() = True
            BTN_SEND.Enabled() = True
            TXT_BOX_COMMAND.Enabled() = True
            TXT_BOX_RECEIVE.Enabled() = True
        Catch ex As Exception
            MessageBox.Show(ex.ToString(), "Error", MessageBoxButtons.OK, MessageBoxIcon.Exclamation)
        End Try
    End Sub


    '****************************************************************
    '*  Disconnect                                                  *
    '****************************************************************
    Private Sub BTN_DIS_CONNECT_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_DIS_CONNECT.Click
        g_TcpClient.Close()
        LBL_STATUS.Text = "Disconnect"
        TXT_BOX_IP.Enabled() = True
        TXT_BOX_PORT.Enabled() = True
        BTN_CONNECT.Enabled() = True
        BTN_DIS_CONNECT.Enabled() = False
        BTN_SEND.Enabled() = False
        TXT_BOX_COMMAND.Enabled() = False
        TXT_BOX_RECEIVE.Enabled() = False
    End Sub


    '****************************************************************
    '*  Transmit the messages                                       *
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
    '*  Transmit and recieve the messages                           *
    '****************************************************************
    Private Sub SendQueryMsg(ByVal strMsg As String)
        Try
            strMsg = strMsg & vbCrLf
            Dim bytesWrite As [Byte]() = Encoding.ASCII.GetBytes(strMsg)
            g_TcpClient.GetStream().Write(bytesWrite, 0, bytesWrite.Length)
            g_strRcv = Nothing
            Dim ASCII As Encoding = Encoding.ASCII
            Dim RecvBytes(255) As [Byte]
            Dim bytes As Int32 = g_TcpClient.GetStream().Read(RecvBytes, 0, RecvBytes.Length)
            g_strRcv = ASCII.GetString(RecvBytes, 0, bytes)
        Catch Ex As Exception
            MsgBox(Ex.Message)
        End Try
    End Sub

    '****************************************************************
    '*  Send the data                                               *
    '****************************************************************
    Private Sub BTN_SEND_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles BTN_SEND.Click
        Dim data As String = TXT_BOX_COMMAND.Text
        If InStr(data, "?") = 0 Then
            SendMsg(data)
            TXT_BOX_RECEIVE.Text = ""
        Else
            SendQueryMsg(data)
            TXT_BOX_RECEIVE.Text = g_strRcv
        End If
    End Sub
End Class
