'****************************************************************************
'*                                                                          *
'*  This program conects to the MEMORY HiCORDR and starts communication.    *
'*                                                                          *
'****************************************************************************

Imports System.Text

Public Class Form1
    Dim g_MsgBuf As String

	Private Sub Button1_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button1.Click
		Try
			SerialPort1.PortName = TextBox1.Text
			SerialPort1.Open()
			Button1.Enabled = False
			Button2.Enabled = True
			Button3.Enabled = True
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
		Catch Ex As Exception
			MsgBox(Ex.Message)
		End Try
	End Sub

	Private Sub Button3_Click(ByVal sender As System.Object, ByVal e As System.EventArgs) Handles Button3.Click
		If InStr(TextBox2.Text, "?") = 0 Then
			SendMsg(TextBox2.Text)
			TextBox3.Text = ""
		Else
			SendQueryMsg(TextBox2.Text)
			TextBox3.Text = g_MsgBuf
		End If

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
End Class
