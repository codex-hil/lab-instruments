'********************************************************************************************
'*                                                                                          *
'*  Check the status of the unit by using ":STATUS?" every 1 second.                        *
'*                                                                                          *
'********************************************************************************************

Public Class Form1
    Dim g_MsgBuf As String

	Private Sub Button1_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button1.Click
		Try
			SerialPort1.PortName = TextBox1.Text
			SerialPort1.Open()
			Button1.Enabled = False
			Button2.Enabled = True
			Button3.Enabled = True
			Button4.Enabled = True
			TextBox2.Enabled = True
		Catch Ex As Exception
			MsgBox(Ex.Message)
		End Try
	End Sub

	Private Sub Button2_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button2.Click
		Try
			SerialPort1.Close()
			Button1.Enabled = True
			Button2.Enabled = False
			Button3.Enabled = False
			TextBox2.Enabled = False
			Button4.Enabled = False
			Timer1.Enabled = False
		Catch Ex As Exception
			MsgBox(Ex.Message)
		End Try
	End Sub

	Private Sub SendMsg(ByVal strMsg As String)
		Try
			strMsg = strMsg & vbCrLf
			SerialPort1.WriteLine(strMsg)
		Catch Ex As Exception
			MsgBox(Ex.Message)
		End Try
	End Sub

	Private Sub SendQueryMsg(ByVal strMsg As String)
		Try
			strMsg = strMsg & vbCrLf
			SerialPort1.WriteLine(strMsg)
			Dim Check As Integer
			g_MsgBuf = Nothing
			Do
				Check = SerialPort1.ReadByte()
				If Chr(Check) = vbLf Then
					Exit Do
				ElseIf Chr(Check) = vbCr Then
				Else
					g_MsgBuf = g_MsgBuf & Chr(Check)
				End If
			Loop
			g_MsgBuf = g_MsgBuf & vbCrLf
		Catch Ex As Exception
			MsgBox(Ex.Message)
		End Try
	End Sub

	Private Sub Button3_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button3.Click
		Timer1.Interval = 1000
		Timer1.Enabled = True
	End Sub

	Private Sub Button4_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button4.Click
		stop_timer()
	End Sub

    Private Sub stop_timer()
        SendMsg(":HEADER OFF")
        Timer1.Enabled = False
        TextBox2.SelectedText = "stop"
    End Sub

	Private Sub Timer1_Tick(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Timer1.Tick
		Dim data As Integer

        SendQueryMsg(":STATUS?")

		data = Val(g_MsgBuf)

		If (data = 0) Then
			TextBox2.SelectedText = "stopping" & vbCrLf
		End If

		If ((data And &H1) <> 0) Then
			TextBox2.SelectedText = "starting" & vbCrLf
		End If

		If ((data And &H2) <> 0) Then
			TextBox2.SelectedText = "storing" & vbCrLf
		End If

		If ((data And &H4) <> 0) Then
			TextBox2.SelectedText = "awaiting trigger" & vbCrLf
		End If

		If ((data And &H8) <> 0) Then
			TextBox2.SelectedText = "pre-trigger wait period" & vbCrLf
		End If

		If ((data And &H10) <> 0) Then
			TextBox2.SelectedText = "acquiring a waveform" & vbCrLf
		End If

		If ((data And &H20) <> 0) Then
			TextBox2.SelectedText = "saving" & vbCrLf
		End If
    End Sub
End Class
