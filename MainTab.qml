/*
	Copyright (C) 2019-2021 Doug McLain

	This program is free software: you can redistribute it and/or modify
	it under the terms of the GNU General Public License as published by
	the Free Software Foundation, either version 3 of the License, or
	(at your option) any later version.

	This program is distributed in the hope that it will be useful,
	but WITHOUT ANY WARRANTY; without even the implied warranty of
	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
	GNU General Public License for more details.

	You should have received a copy of the GNU General Public License
	along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

Item {
	id: mainTab
	property int rows: {
		if(USE_FLITE){
            mainTab.rows = 20;
		}
		else{
            mainTab.rows = 18;
		}
	}
	property bool tts: {
		if(USE_FLITE){
			tts = true;
		}
		else{
			tts = false;
		}
	}

	onWidthChanged:{
        if(_comboMode.currentText === "DMR"){
			_comboMode.width = (mainTab.width / 5) - 5;
			_connectbutton.width = (mainTab.width * 2 / 5 ) - 5
			_connectbutton.x = (mainTab.width * 3 / 5 )
		}
		else{
			_comboMode.width = (mainTab.width / 2) - 5;
			_connectbutton.width = (mainTab.width / 2) - 5;
			_connectbutton.x = mainTab.width / 2;
		}
	}

	property alias element3: _element3
	property alias label1: _label1
	property alias label2: _label2
	property alias label3: _label3
	property alias label4: _label4
	property alias label5: _label5
	property alias label6: _label6
	property alias ambestatus: _ambestatus
	property alias mmdvmstatus: _mmdvmstatus
	property alias netstatus: _netstatus
	property alias levelMeter: _levelMeter
	property alias uitimer: _uitimer
	property alias comboMode: _comboMode
	property alias comboHost: _comboHost
	property alias dtmflabel: _dtmflabel
	property alias editIAXDTMF: _editIAXDTMF
	property alias dtmfsendbutton: _dtmfsendbutton
	property alias comboModule: _comboModule
	property alias comboSlot: _comboSlot
	property alias comboCC: _comboCC
	property alias dmrtgidEdit: _dmrtgidEdit
	property alias comboM17CAN: _comboM17CAN
	property alias privateBox: _privateBox
	property alias connectbutton: _connectbutton
	property alias sliderMicGain: _slidermicGain
	property alias data1: _data1
	property alias data2: _data2
	property alias data3: _data3
	property alias data4: _data4
	property alias data5: _data5
	property alias data6: _data6
	property alias txtimer: _txtimer
	property alias buttonTX: _buttonTX
	property alias btntxt: _btntxt
	property alias swtxBox: _swtxBox
	property alias swrxBox: _swrxBox
	property alias agcBox: _agcBox

	Timer {
		id: _uitimer
		interval: 20; running: true; repeat: true
		property int cnt: 0;
		property int rxcnt: 0;
		property int last_rxcnt: 0;
		onTriggered: update_level();

		function update_level(){
			if(cnt >= 20){
				if(rxcnt == last_rxcnt){
                    droidstar.set_output_level(0);
					rxcnt = 0;
					//console.log("TIMEOUT");
				}
				else{
					last_rxcnt = rxcnt;
				}

				cnt = 0;
			}
			else{
				++cnt;
			}

			var l = (parent.width - 20) * droidstar.get_output_level() / 32767.0;
			if(l > _levelMeter.width){
				_levelMeter.width = l;
			}
			else{
				if(_levelMeter.width > 0)
					_levelMeter.width -= 8;
				else
					_levelMeter.width = 0;
			}
		}
	}
	// --- legacy DroidStar controls, kept intact and hidden; the workspace below drives them ---
	Item { id: _legacy; anchors.fill: parent; visible: false
	ComboBox {
		id: _comboMode
		property bool loaded: false
		x: 5
		y: 0
		width: (parent.width / 2) - 5
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 40
		currentIndex: -1
			displayText: currentIndex === -1 ? "Mode..." : currentText
		model: ["M17", "YSF", "FCS", "DMR", "P25", "NXDN", "REF", "XRF", "DCS", "IAX"]
		contentItem: Text {
			text: _comboMode.displayText
			font: _comboMode.font
			leftPadding: 10
			verticalAlignment: Text.AlignVCenter
			color: _comboMode.enabled ? "white" : "darkgrey"
		}
		onCurrentTextChanged: {
			if(_comboMode.loaded){
				droidstar.process_mode_change(_comboMode.currentText);
			}
			if(_comboMode.currentText == "DMR"){
				_comboMode.width = (mainTab.width / 5) - 5;
				_connectbutton.width = (mainTab.width * 2 / 5 ) - 5;
				_connectbutton.x = (mainTab.width * 3 / 5 );
			}
			else{
				_comboMode.width = (mainTab.width / 2) - 5;
				_connectbutton.width = (mainTab.width / 2) - 5;
				_connectbutton.x = mainTab.width / 2;
			}
		}
	}
	ComboBox {
		id: _comboSlot
		x: (parent.width / 5 )
		y: 0
		width: (parent.width / 5)
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 35
		model: ["S1", "S2"]
		currentIndex: 1
		contentItem: Text {
			text: _comboSlot.displayText
			font: _comboSlot.font
			leftPadding: 10
			verticalAlignment: Text.AlignVCenter
			color: _comboSlot.enabled ? "white" : "darkgrey"
		}
		onCurrentTextChanged: {
			droidstar.set_slot(_comboSlot.currentIndex);
		}
		visible: false
	}
	ComboBox {
		id: _comboCC
		x: (parent.width * 2 / 5 )
		y: 0
		width: (parent.width / 5)
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 35
		model: ["CC0", "CC1", "CC2", "CC3", "CC4", "CC5", "CC6", "CC7", "CC8", "CC9", "CC10", "CC11", "CC12", "CC13", "CC14", "CC15"]
		currentIndex: 1
		contentItem: Text {
			text: _comboCC.displayText
			font: _comboCC.font
			leftPadding: 10
			verticalAlignment: Text.AlignVCenter
			color: _comboCC.enabled ? "white" : "darkgrey"
		}
		onCurrentTextChanged: {
			droidstar.set_cc(_comboCC.currentIndex);
		}
		visible: false
	}
	Button {
		id: _connectbutton
		x: parent.width / 2
		y: 0
		width: parent.width / 2
        height: parent.height / mainTab.rows
		text: qsTr("Connect")
		font.pixelSize: parent.height / 30
		onClicked: {
			//settingsTab.callsignEdit.text = settingsTab.callsignEdit.text.toUpperCase();
			droidstar.set_callsign(settingsTab.callsignEdit.text.toUpperCase());
			//droidstar.set_host(comboHost.currentText);
			droidstar.set_module(comboModule.currentText);
			droidstar.set_protocol(comboMode.currentText);
			droidstar.set_dmrtgid(dmrtgidEdit.text);
			droidstar.set_dmrid(settingsTab.dmridEdit.text);
			droidstar.set_essid(settingsTab.comboEssid.currentText);
			droidstar.set_bm_password(settingsTab.bmpwEdit.text);
			droidstar.set_tgif_password(settingsTab.tgifpwEdit.text);
			droidstar.set_adn_password(settingsTab.adnpwEdit.text);
			droidstar.set_asl_password(settingsTab.aslpwEdit.text);
			droidstar.set_latitude(settingsTab.latEdit.text);
			droidstar.set_longitude(settingsTab.lonEdit.text);
			droidstar.set_location(settingsTab.locEdit.text);
			droidstar.set_description(settingsTab.descEdit.text);
			droidstar.set_url(settingsTab.urlEdit.text);
			droidstar.set_swid(settingsTab.swidEdit.text);
			droidstar.set_pkgid(settingsTab.pkgidEdit.text);
			droidstar.set_dmr_options(settingsTab.dmroptsEdit.text);
			droidstar.set_dmr_pc(mainTab.privateBox.checked);
			droidstar.set_txtimeout(settingsTab.txtimerEdit.text);
			//droidstar.set_toggletx(toggleTX.checked);
			droidstar.set_xrf2ref(settingsTab.xrf2ref.checked);
			droidstar.set_ipv6(settingsTab.ipv6.checked);
			droidstar.set_vocoder(settingsTab.comboVocoder.currentText);
			droidstar.set_modem(settingsTab.comboModem.currentText);
			droidstar.set_playback(settingsTab.comboPlayback.currentText);
			droidstar.set_capture(settingsTab.comboCapture.currentText);

			droidstar.set_modemRxFreq(settingsTab.modemRXFreqEdit.text);
			droidstar.set_modemTxFreq(settingsTab.modemTXFreqEdit.text);
			droidstar.set_modemRxOffset(settingsTab.modemRXOffsetEdit.text);
			droidstar.set_modemTxOffset(settingsTab.modemTXOffsetEdit.text);
			droidstar.set_modemRxDCOffset(settingsTab.modemRXDCOffsetEdit.text);
			droidstar.set_modemTxDCOffset(settingsTab.modemTXDCOffsetEdit.text);
			droidstar.set_modemRxLevel(settingsTab.modemRXLevelEdit.text);
			droidstar.set_modemTxLevel(settingsTab.modemRXLevelEdit.text);
			droidstar.set_modemRFLevel(settingsTab.modemRFLevelEdit.text);
			droidstar.set_modemTxDelay(settingsTab.modemTXDelayEdit.text);
			droidstar.set_modemCWIdTxLevel(settingsTab.modemCWIdTXLevelEdit.text);
			droidstar.set_modemDstarTxLevel(settingsTab.modemDStarTXLevelEdit.text);
			droidstar.set_modemDMRTxLevel(settingsTab.modemDMRTXLevelEdit.text);
			droidstar.set_modemYSFTxLevel(settingsTab.modemYSFTXLevelEdit.text);
			droidstar.set_modemP25TxLevel(settingsTab.modemYSFTXLevelEdit.text);
			droidstar.set_modemNXDNTxLevel(settingsTab.modemNXDNTXLevelEdit.text);
			droidstar.set_modemBaud(settingsTab.modemBaudEdit.text);
			//droidstar.set_mmdvm_direct(settingsTab.mmdvmBox.checked)
			droidstar.process_connect();
		}
	}
	ComboBox {
		id: _comboHost
		x: 5
        y: (parent.height / mainTab.rows + 1) * 1;
		width: ((parent.width * 3) / 4) - 5
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 35
		currentIndex: -1
		displayText: currentIndex === -1 ? "Host..." : currentText

		// The model stays the full, unfiltered host list so that currentIndex always
		// means "index into the host list", whatever is typed in the search box.  Only
		// the popup's list is filtered, and it holds indices into this model.
		// See _hostList.filteredIndices below.
		readonly property int popupRowHeight: _comboHost.height
		readonly property int popupVisibleRows: 12

		function selectHost(sourceIndex) {
			_comboHost.currentIndex = sourceIndex;
			_comboHost.activated(sourceIndex);
			_comboHost.popup.close();
		}

		popup: Popup {
			id: _comboHostPopup
			y: _comboHost.height - 1
			width: _comboHost.width
			padding: 1

			background: Rectangle {
				color: "#252424"
				border.color: "#555555"
			}

			onOpened: {
				_hostFilter.text = "";
				var i = _hostList.filteredIndices.indexOf(_comboHost.currentIndex);
				_hostList.currentIndex = (i < 0) ? 0 : i;
				if(_hostList.count > 0){
					_hostList.positionViewAtIndex(_hostList.currentIndex, ListView.Contain);
				}
				_hostFilter.forceActiveFocus();
			}

			contentItem: Item {
				implicitHeight: _hostFilter.height + _hostList.height

				TextField {
					id: _hostFilter
					width: parent.width
					height: _comboHost.popupRowHeight
					font: _comboHost.font
					color: "white"
					placeholderText: qsTr("Search...")

					background: Rectangle {
						color: "#353535"
					}

					onDisplayTextChanged: _hostList.currentIndex = 0
					onAccepted: {
						if(_hostList.currentItem !== null){
							_comboHost.selectHost(_hostList.currentItem.modelData);
						}
					}
					Keys.onDownPressed: _hostList.incrementCurrentIndex()
					Keys.onUpPressed: _hostList.decrementCurrentIndex()
				}
				ListView {
					id: _hostList
					anchors.top: _hostFilter.bottom
					width: parent.width
					height: _comboHost.popupRowHeight * Math.min(count, _comboHost.popupVisibleRows)
					clip: true
					currentIndex: 0

					// Indices into the ComboBox's unfiltered model whose host matches
					// the search text.
					readonly property var filteredIndices: {
						var out = [];
						var needle = _hostFilter.displayText.toLowerCase();
						for(var i = 0; i < _comboHost.count; ++i){
							if((needle === "") || (_comboHost.textAt(i).toLowerCase().indexOf(needle) >= 0)){
								out.push(i);
							}
						}
						return out;
					}
					model: filteredIndices

					ScrollBar.vertical: ScrollBar {
						active: true
					}

					delegate: ItemDelegate {
						id: _hostDelegate
						width: ListView.view.width
						height: _comboHost.popupRowHeight

						// the list model holds indices into the ComboBox's model
						required property int modelData
						required property int index

						background: Rectangle {
							color: _hostDelegate.highlighted ? "steelblue" : "#252424"
						}

						contentItem: Text {
							text: _comboHost.textAt(_hostDelegate.modelData)
							font: _comboHost.font
							leftPadding: 10
							elide: Text.ElideRight
							verticalAlignment: Text.AlignVCenter
							color: "white"
						}

						highlighted: _hostList.currentIndex === _hostDelegate.index

						onClicked: _comboHost.selectHost(_hostDelegate.modelData)
						onHoveredChanged: {
							if(hovered){
								_hostList.currentIndex = _hostDelegate.index;
							}
						}
					}
				}
			}
		}
		contentItem: Text {
			text: _comboHost.displayText
			font: _comboHost.font
			leftPadding: 10
			verticalAlignment: Text.AlignVCenter
			color: _comboHost.enabled ? "white" : "darkgrey"
		}
		onCurrentTextChanged: {
			if(settingsTab.mmdvmBox.checked){
				droidstar.set_dst(_comboHost.currentText);
			}
			if(!droidstar.get_modelchange()){
				droidstar.process_host_change(_comboHost.currentText);
			}
		}
	}
	ComboBox {
		id: _comboModule
		x: ((parent.width * 3) / 4)
        y: (parent.height / mainTab.rows + 1) * 1
		width: (parent.width / 4) - 5
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 35
		currentIndex: -1
			displayText: currentIndex === -1 ? "Mod..." : currentText
		model: [" ", "A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W", "X", "Y", "Z", " ", " "]
		contentItem: Text {
			text: _comboModule.displayText
			font: _comboModule.font
			leftPadding: 10
			verticalAlignment: Text.AlignVCenter
			color: _comboModule.enabled ? "white" : "darkgrey"
		}
		onCurrentTextChanged: {
			if(_comboMode.loaded){
				droidstar.set_module(_comboModule.currentText);
			}
		}
	}
	CheckBox {
		id: _privateBox
		x: ((parent.width * 3) / 4)
        y: (parent.height / mainTab.rows + 1) * 1;
		width: (parent.width / 4) - 5
        height: parent.height / mainTab.rows
		text: qsTr("Private")
		onClicked:{
			droidstar.set_dmr_pc(privateBox.checked)
			//console.log("screen size ", parent.width, " x ", parent.height);
		}
		visible: false
	}
	Text {
		id: _dtmflabel
		x: 5
		y: (parent.height / mainTab.rows + 1) * 4;
		width: parent.width / 5
        height:  parent.height / mainTab.rows;
		text: qsTr("DTMF")
		color: "white"
		font.pixelSize: parent.height / 30;
		verticalAlignment: Text.AlignVCenter
		visible: false
	}
	TextField {
		id: _editIAXDTMF
		x: (parent.width / 4)
		y: (parent.height / mainTab.rows + 1) * 4;
		width: (parent.width * 3 / 8) - 4;
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 35
		//inputMethodHints: "ImhPreferNumbers"
		visible: false
	}
	Button {
		id: _dtmfsendbutton
		x: (parent.width * 5 / 8)
		y: (parent.height / mainTab.rows + 1) * 4;
		width: (parent.width * 3 / 8) - 5;
        height: parent.height / mainTab.rows;
		text: qsTr("Send")
		font.pixelSize: parent.height / 30
		onClicked: {
			droidstar.dtmf_send_clicked(editIAXDTMF.text);
		}
		visible: false
	}
	Text {
		id: _element3
		x: 5
        y: (parent.height / mainTab.rows + 1) * 2;
		width: parent.width / 5
        height:  parent.height / mainTab.rows;
		text: qsTr("TGID")
		color: "white"
		font.pixelSize: parent.height / 30;
		verticalAlignment: Text.AlignVCenter
		visible: false
	}
	TextField {
		visible: false
		id: _dmrtgidEdit
		x: parent.width / 5
        y: (parent.height / mainTab.rows + 1) * 2
		width: parent.width / 5
        height: parent.height / mainTab.rows
		font.pixelSize: parent.height / 35
		selectByMouse: true
		inputMethodHints: "ImhPreferNumbers"
		text: qsTr("")
		onEditingFinished: {
			droidstar.tgid_text_changed(dmrtgidEdit.text)
		}
	}
	ComboBox {
		visible: false
		id: _comboM17CAN
		x: parent.width / 5
        y:  (parent.height / mainTab.rows + 1) * 2
		width: parent.width / 5
        height: parent.height / mainTab.rows;
		font.pixelSize: parent.height / 35
		currentIndex: 0
		model: ["0", "1", "2", "3", "4", "5", "6", "7"]
		contentItem: Text {
			text: _comboM17CAN.displayText
			font: _comboM17CAN.font
			leftPadding: 10
			verticalAlignment: Text.AlignVCenter
			color: _comboM17CAN.enabled ? "white" : "darkgrey"
		}
		onCurrentTextChanged: {
			droidstar.set_modemM17CAN(_comboM17CAN.currentText);
		}
	}
	CheckBox {
		id: _swtxBox
		x: (parent.width * 2 / 5) + 5
		y: (parent.height / mainTab.rows + 1) * 2;
		width: parent.width / 4
		height: parent.height / mainTab.rows
		font.pixelSize: parent.height / 40;
		text: qsTr("SWTX")
		onClicked:{
			droidstar.set_swtx(_swtxBox.checked)
		}
	}
	CheckBox {
		id: _swrxBox
		x: (parent.width * 3 / 5) + 5
        y: (parent.height / mainTab.rows + 1) * 2;
		width: parent.width / 4
        height: parent.height / mainTab.rows
		font.pixelSize: parent.height / 40;
		text: qsTr("SWRX")
		onClicked:{
			droidstar.set_swrx(_swrxBox.checked)
		}
	}

	CheckBox {
		id: _agcBox
		x: (parent.width * 4 / 5) + 5
        y: (parent.height / mainTab.rows + 1) * 2;
		width: parent.width / 4
        height: parent.height / mainTab.rows
		font.pixelSize: parent.height / 40;
		text: qsTr("AGC")
		onClicked:{
			droidstar.set_agc(_agcBox.checked)
		}
	}
	Text {
		id: micgain_label
		x: 10
        y: (parent.height / mainTab.rows + 1) * 3;
		width: parent.width / 4;
        height: parent.height / mainTab.rows;
		text: qsTr("Mic")
		color: "white"
		font.pixelSize: parent.height / 40;
		verticalAlignment: Text.AlignVCenter
	}
	Slider {
		property double v;
		visible: true
		id: _slidermicGain
		x: (parent.width / 4) + 10
        y: (parent.height / mainTab.rows + 1) * 3;
		width: (parent.width * 3 / 4) - 20
        height: parent.height / mainTab.rows;
		value: 0.1
		onValueChanged: {
			v = value * 100;
			droidstar.set_input_volume(value);
			micgain_label.text = "Mic " + v.toFixed(1);
		}
	}
	Text {
		id: _label1
		x: 10
        y: (parent.height / mainTab.rows + 1) * 4;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("MYCALL")
		color: "white"
		font.pixelSize: parent.height / 30;
	}
	Text {
		id: _label2
		x: 10
        y: (parent.height / mainTab.rows + 1) * 5;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("URCALL")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _label3
		x: 10
        y: (parent.height / mainTab.rows + 1) * 6;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("RPTR1")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _label4
		x: 10
        y: (parent.height / mainTab.rows + 1) * 7;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("RPTR2")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _label5
		x: 10
        y: (parent.height / mainTab.rows + 1) * 8;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("StrmID")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _label6
		x: 10
        y: (parent.height / mainTab.rows + 1) * 9;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("Text")
		color: "white"
		font.pixelSize: parent.height / 30;
	}
	Text {
		id: _label7
		x: 10
        y: (parent.height / mainTab.rows + 1) * 10;
		width: parent.width / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}
	Text {
		id: _data1
		x: parent.width / 3
        y: (parent.height / mainTab.rows + 1) * 4;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _data2
		x: parent.width / 3
        y: (parent.height / mainTab.rows + 1) * 5;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _data3
		x: parent.width / 3
        y: (parent.height / mainTab.rows + 1) * 6;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _data4
		x: parent.width / 3
        y: (parent.height / mainTab.rows + 1) * 7;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _data5
		x: parent.width / 3
        y: (parent.height / mainTab.rows + 1) * 8;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _data6
		x: parent.width / 3
        y:(parent.height / mainTab.rows + 1) * 9;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}
	Text {
		id: _data7
		x: parent.width / 3
        y:(parent.height / mainTab.rows + 1) * 10;
		width: (parent.width * 2) / 3
        height: parent.height / mainTab.rows;
		text: qsTr("")
		color: "white"
		font.pixelSize: parent.height / 30;
	}

	Text {
		id: _ambestatus
		x: 10
        y: (parent.height / mainTab.rows + 1) * 11;
		width: parent.width - 20
        height: parent.height / mainTab.rows;
		text: qsTr("No AMBE hardware connected")
		color: "white"
		font.pixelSize: parent.height / 35;
	}
	Text {
		id: _mmdvmstatus
		x: 10
        y: (parent.height / mainTab.rows + 1) * 12;
		width: parent.width - 20
        height: parent.height / mainTab.rows;
		text: qsTr("No MMDVM connected")
		color: "white"
		font.pixelSize: parent.height / 35;
	}
	Text {
		id: _netstatus
		x: 10
        y: (parent.height / mainTab.rows + 1) * 13;
		width: parent.width - 20
        height: parent.height / mainTab.rows;
		text: qsTr("Not Connected to network")
		color: "white"
		font.pixelSize: parent.height / 35;
	}
	Rectangle {
		x: 10
        y: (parent.height / mainTab.rows + 1) * 14;
		width: parent.width - 20
		height: parent.height / 30;
		color: "black"
		border.color: "black"
		border.width: 1
		radius: 5
	}
	Rectangle {
		id: _levelMeter
		x: 10
        y: (parent.height / mainTab.rows + 1) * 14;
		width: 0
		height: parent.height / 30;
		color: "#80C342"
		border.color: "black"
		border.width: 1
		radius: 5
	}
	ButtonGroup {
		id: ttsvoicegroup
		onClicked: {
			droidstar.tts_changed(button.text);
		}
	}
	CheckBox {
		id: mic
        visible: mainTab.tts ? true : false;
		x: 5
        y: (parent.height / mainTab.rows + 1) * 15;
		height: 25
		spacing: 1
		text: qsTr("Mic")
		checked: true
		ButtonGroup.group: ttsvoicegroup
	}
	CheckBox {
		id: tts1
        visible: mainTab.tts ? true : false;
		x: parent.width / 4
        y: (parent.height / mainTab.rows + 1) * 15;
		height: 25
		spacing: 1
		text: qsTr("TTS1")
		ButtonGroup.group: ttsvoicegroup
	}
	CheckBox {
		id: tts2
        visible: mainTab.tts ? true : false;
		x: parent.width * 2 / 4
        y: (parent.height / mainTab.rows + 1) * 15;
		height: 25
		spacing: 1
		text: qsTr("TTS2")
		checked: true
		ButtonGroup.group: ttsvoicegroup
	}
	CheckBox {
		id: tts3
        visible: mainTab.tts ? true : false;
		x: parent.width * 3 / 4
        y: (parent.height / mainTab.rows + 1) * 15;
		height: 25
		spacing: 1
		text: qsTr("TTS3")
		ButtonGroup.group: ttsvoicegroup
	}
	TextField {
		id: _ttstxtedit
        visible: mainTab.tts ? true : false;
		x: 5
        y: (parent.height / mainTab.rows + 1) * 16;
		width: parent.width - 10
        height: parent.height / mainTab.rows
		font.pixelSize: parent.height / 35
		selectByMouse: true
		inputMethodHints: "ImhPreferNumbers"
		text: qsTr("")
		onEditingFinished: {
			droidstar.tts_text_changed(_ttstxtedit.text)
		}
	}
	Button {
		Timer {
			id: _txtimer
			repeat: true;
			onTriggered: {
				++buttonTX.cnt;
				btntxt.text = "TX: " + buttonTX.cnt;
				if(buttonTX.cnt >= parseInt(settingsTab.txtimerEdit.text)){
					buttonTX.tx = false;
					droidstar.click_tx(buttonTX.tx);
					_txtimer.running = false;
					_btntxt.text = "TX";
				}
			}
		}

		property bool tx: false
		property int cnt: 0
		visible: true
		enabled: false
		id: _buttonTX
		background: Rectangle {
			color: _buttonTX.tx ? "#800000" : "steelblue" //"#80c342"
			radius: 10
			Text {
				id:_btntxt
				anchors.centerIn: parent
				font.pointSize: 18
				text: qsTr("TX")
			}
		}
		x: 10
        y: (parent.height / mainTab.rows + 1) * ( mainTab.tts ? 17 : 15);
		//y: parent.height - ((parent.height / 5) + 5);
		width: parent.width - 20
		height: parent.height - y - 10
		//text: qsTr("TX")
		font.pointSize: 24
		onClicked: {
			if(settingsTab.toggleTX.checked){
				tx = !tx;
				droidstar.click_tx(tx);
				if(tx){
					cnt = 0;
					_txtimer.running = true;
					_btntxt.color = "white";
				}
				else{
					_txtimer.running = false;
					btntxt.color = "black";
					_btntxt.text = "TX";
				}
			}
		}
		onPressed: {
			if(!settingsTab.toggleTX.checked){
				tx = true;
				droidstar.press_tx();
			}
		}
		onReleased: {
			if(!settingsTab.toggleTX.checked){
				tx = false;
				droidstar.release_tx();
			}
		}
		onCanceled: {
			if(!settingsTab.toggleTX.checked){
				tx = false;
				droidstar.release_tx();
			}
		}
	}
	} // end _legacy (hidden DroidStar controls; the workspace below drives them)

	// ===================== HELLAS ZONE workspace =====================
	// Original QML UI that drives the (hidden) DroidStar controls above by id.
    Rectangle {
        id: ws
        anchors.fill: parent
        color: bg

        readonly property color bg:    "#090a10"
        readonly property color rail:  "#0c0d15"
        readonly property color panel: "#0f111c"
        readonly property color panel2:"#141829"
        readonly property color line:  "#1d2234"
        readonly property color line2: "#2a3148"
        readonly property color text:  "#eef1f7"
        readonly property color text2: "#aab3c4"
        readonly property color muted: "#6b7488"
        readonly property color dim:   "#4e5568"
        readonly property color acc:   "#8b7cf6"
        readonly property color acc2:  "#a78bfa"
        readonly property color rxc:   "#37d98a"
        readonly property color txc:   "#ffab42"
        readonly property color danger:"#ff5a6e"
        readonly property color cyan:  "#40b8e8"

        property string curNet: "C4FM"
        property string selHost: ""
        property bool   listening: false
        property bool   connected: (_connectbutton.text === "Disconnect")
        property bool   connecting: (_connectbutton.text === "Connecting")
        property string search: ""

        property var nets: [
            {label:"DMR",      mode:"DMR", col:"#a78bfa"},
            {label:"D-Star",   mode:"REF", col:"#f2a93c"},
            {label:"EchoLink", mode:"IAX", col:"#40b8e8"},
            {label:"C4FM",     mode:"YSF", col:"#ff6fae"}
        ]
        function netCol(n){ for(var i=0;i<nets.length;i++) if(nets[i].label===n) return nets[i].col; return acc }
        function netMode(n){ for(var i=0;i<nets.length;i++) if(nets[i].label===n) return nets[i].mode; return "YSF" }
        function provider(){ var m=_comboMode.currentText; if(m==="DMR") return "BrandMeister"; if(m==="REF"||m==="XRF"||m==="DCS") return "Reflectors"; if(m==="IAX") return "EchoLink"; return "YSF" }

        property var filteredHosts: {
            var _n=_comboHost.count; var _m=_comboMode.currentText; var q=ws.search.toLowerCase();
            var src=_comboHost.model; var a=[];
            if(src){ for(var i=0;i<src.length;i++){ var t=String(src[i]); if(q==="" || t.toLowerCase().indexOf(q)>=0) a.push(t); } }
            return a;
        }
        function selectMode(mode,label){ ws.curNet=label; ws.selHost=""; ws.search=""; ws.listening=false; _comboMode.loaded=true; var ix=_comboMode.find(mode); if(ix>=0) _comboMode.currentIndex=ix; }
        function selectHost(h){ ws.selHost=h; var ix=_comboHost.find(h); if(ix>=0) _comboHost.currentIndex=ix; }
        function doConnect(){ if(!ws.connected && !ws.connecting && ws.selHost!=="") _connectbutton.clicked() }
        function doStop(){ if(ws.connected || ws.connecting) _connectbutton.clicked(); ws.listening=false }

        property string clockUtc: ""
        property string clockLocal: ""
        function pad(n){ return (n<10?"0":"")+n }
        function tick(){ var d=new Date(); ws.clockUtc=pad(d.getUTCHours())+":"+pad(d.getUTCMinutes())+":"+pad(d.getUTCSeconds()); ws.clockLocal=pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds()) }
        Timer { interval:1000; running:true; repeat:true; triggeredOnStart:true; onTriggered: ws.tick() }
        Component.onCompleted: { ws.tick(); _comboMode.loaded=true; var ix=_comboMode.find(ws.netMode(ws.curNet)); if(ix>=0) _comboMode.currentIndex=ix }

        RowLayout {
            anchors.fill: parent
            spacing: 0

            // ---------- LEFT RAIL ----------
            Rectangle {
                Layout.preferredWidth: 86; Layout.fillHeight: true; color: ws.rail
                ColumnLayout {
                    anchors.fill: parent; anchors.topMargin: 14; anchors.bottomMargin: 14; spacing: 6
                    Rectangle {
                        Layout.alignment: Qt.AlignHCenter; width: 50; height: 50; radius: 14
                        gradient: Gradient { GradientStop{position:0;color:ws.acc2} GradientStop{position:1;color:ws.acc} }
                        Text { anchors.centerIn: parent; text: "☷"; color: "white"; font.pixelSize: 22 }
                    }
                    Item { height: 8 }
                    Repeater {
                        model: ["▦","✚","☰","☷","◷","🎧","○"]
                        delegate: Rectangle {
                            required property var modelData
                            required property int index
                            Layout.alignment: Qt.AlignHCenter; width: 44; height: 40; radius: 11
                            color: index===5 ? Qt.rgba(0.54,0.49,0.96,0.16) : "transparent"
                            Text { anchors.centerIn: parent; text: modelData; color: index===5?ws.acc2:ws.muted; font.pixelSize: 17 }
                        }
                    }
                    Item { Layout.fillHeight: true }
                    Repeater {
                        model: ["⤓","?","⚙"]
                        delegate: Rectangle { required property var modelData; Layout.alignment: Qt.AlignHCenter; width: 44; height: 36; color: "transparent"
                            Text { anchors.centerIn: parent; text: modelData; color: ws.muted; font.pixelSize: 16 } }
                    }
                    Rectangle { Layout.alignment: Qt.AlignHCenter; width: 36; height: 36; radius: 18; color: ws.panel2; border.color: ws.line2
                        Text { anchors.centerIn: parent; text: "SA"; color: ws.text; font.pixelSize: 12; font.bold: true } }
                }
            }

            // ---------- MAIN ----------
            ColumnLayout {
                Layout.fillWidth: true; Layout.fillHeight: true; spacing: 0

                // top bar
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 58; color: ws.rail
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 20; anchors.rightMargin: 20; spacing: 12
                        Column {
                            Layout.alignment: Qt.AlignVCenter
                            Text { text: "HELLAS ZONE +"; color: ws.muted; font.pixelSize: 10; font.letterSpacing: 2 }
                            Text { text: "DIGI <font color='"+ws.acc2+"'>CONNECT</font>"; textFormat: Text.RichText; color: ws.text; font.pixelSize: 19; font.bold: true }
                        }
                        Item { Layout.fillWidth: true }
                        Column {
                            Layout.alignment: Qt.AlignVCenter
                            Row { spacing: 5; anchors.right: parent.right
                                Text { text: ws.clockUtc; color: ws.text; font.pixelSize: 15; font.bold: true }
                                Text { text: "UTC"; color: ws.muted; font.pixelSize: 9; anchors.bottom: parent.bottom; anchors.bottomMargin: 2 } }
                            Text { text: ws.clockLocal+" PM"; color: ws.muted; font.pixelSize: 11; anchors.right: parent.right }
                        }
                        Text { text: (settingsTab.callsignEdit.text==="" ? "NOCALL" : settingsTab.callsignEdit.text); color: ws.text; font.pixelSize: 14; font.bold: true }
                        Rectangle { implicitHeight: 34; implicitWidth: 104; radius: 9; color: ws.panel; border.color: ws.line2
                            Row { anchors.centerIn: parent; spacing: 6
                                Text { text: "⚙"; color: ws.text2; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: "Settings"; color: ws.text; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter } } }
                    }
                }

                // header
                Item {
                    Layout.fillWidth: true; implicitHeight: 72
                    RowLayout {
                        anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; spacing: 10
                        Column {
                            Layout.alignment: Qt.AlignVCenter; spacing: 3
                            Text { text: "Radio workspace <font color='"+ws.netCol(ws.curNet)+"'>"+ws.curNet+"</font>"; textFormat: Text.RichText; color: ws.text; font.pixelSize: 25; font.bold: true }
                            Text { text: "Choose a station, then Listen. Connect transmission separately to participate."; color: ws.muted; font.pixelSize: 12 }
                        }
                        Item { Layout.fillWidth: true }
                        Rectangle { implicitHeight: 36; implicitWidth: 104; radius: 9; color: ws.panel; border.color: ws.line2
                            Text { anchors.centerIn: parent; text: "+ New QSO"; color: ws.text; font.pixelSize: 13 } }
                        Rectangle { implicitHeight: 36; implicitWidth: 100; radius: 9; color: ws.panel; border.color: ws.line2
                            Text { anchors.centerIn: parent; text: "⚙ Settings"; color: ws.text; font.pixelSize: 13 } }
                    }
                }

                // network tabs
                Flow {
                    Layout.fillWidth: true; Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.bottomMargin: 12; spacing: 8
                    Rectangle {
                        implicitHeight: 38; implicitWidth: favr.implicitWidth+24; radius: 10; color: ws.panel; border.color: ws.line2
                        Row { id: favr; anchors.centerIn: parent; spacing: 8
                            Text { text: "▦"; color: ws.text2; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                            Text { text: "My favorites"; color: ws.text; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
                            Rectangle { width: 20; height: 20; radius: 6; color: ws.acc; anchors.verticalCenter: parent.verticalCenter
                                Text { anchors.centerIn: parent; text: "4"; color: "#0a0a14"; font.pixelSize: 11; font.bold: true } } }
                    }
                    Repeater {
                        model: ws.nets
                        delegate: Rectangle {
                            required property var modelData
                            implicitHeight: 38; implicitWidth: tr.implicitWidth+26; radius: 10
                            property bool on: ws.curNet===modelData.label
                            color: on ? Qt.rgba(0.54,0.49,0.96,0.14) : ws.panel
                            border.color: on ? modelData.col : ws.line2
                            Row { id: tr; anchors.centerIn: parent; spacing: 9
                                Rectangle { width: 9; height: 9; radius: 5; color: modelData.col; anchors.verticalCenter: parent.verticalCenter }
                                Text { text: modelData.label; color: on?ws.text:ws.text2; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter } }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ws.connected && !ws.connecting; onClicked: ws.selectMode(modelData.mode, modelData.label) }
                        }
                    }
                }

                // three columns
                RowLayout {
                    Layout.fillWidth: true; Layout.fillHeight: true
                    Layout.leftMargin: 22; Layout.rightMargin: 22; Layout.bottomMargin: 14; spacing: 14

                    // ===== DIRECTORY =====
                    Rectangle {
                        Layout.fillHeight: true; Layout.fillWidth: true; Layout.preferredWidth: 52
                        radius: 14; color: ws.panel; border.color: ws.line
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 16; spacing: 10
                            RowLayout {
                                Layout.fillWidth: true; spacing: 8
                                Rectangle { radius: 9; color: ws.panel2; border.color: ws.line2; implicitHeight: 34; implicitWidth: 230
                                    Row { anchors.fill: parent; anchors.margins: 3
                                        Rectangle { width: 120; height: parent.height; radius: 7; color: Qt.rgba(0.54,0.49,0.96,0.18)
                                            Text { anchors.centerIn: parent; text: ws.curNet==="DMR"?"TG catalogue":"Station directory"; color: ws.acc2; font.pixelSize: 12; font.bold: true } }
                                        Rectangle { width: 100; height: parent.height; color: "transparent"
                                            Text { anchors.centerIn: parent; text: "My favorites"; color: ws.muted; font.pixelSize: 12 } } } }
                                Item { Layout.fillWidth: true }
                                Rectangle { implicitHeight: 30; implicitWidth: 72; radius: 8; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.centerIn: parent; text: "Refresh"; color: ws.text2; font.pixelSize: 12 }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { _comboMode.loaded=true; droidstar.process_mode_change(_comboMode.currentText) } } }
                            }
                            Rectangle {
                                Layout.fillWidth: true; implicitHeight: 40; radius: 10; color: ws.panel2; border.color: ws.line2
                                Row { anchors.fill: parent; anchors.leftMargin: 12; spacing: 9
                                    Text { text: "🔍"; color: ws.muted; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
                                    TextInput { id: si; width: parent.width-44; anchors.verticalCenter: parent.verticalCenter; color: ws.text; font.pixelSize: 13; clip: true; onTextChanged: ws.search=text
                                        Text { visible: si.text===""; text: "Search TG, name or callsign…"; color: ws.muted; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter } } }
                            }
                            RowLayout {
                                Layout.fillWidth: true; spacing: 8
                                Rectangle { Layout.fillWidth: true; implicitHeight: 36; radius: 9; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "All countries"; color: ws.text2; font.pixelSize: 12 }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: ws.muted; font.pixelSize: 14 } }
                                Rectangle { visible: ws.curNet==="D-Star"; Layout.preferredWidth: 120; implicitHeight: 36; radius: 9; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "All protocols"; color: ws.text2; font.pixelSize: 12 } }
                                Rectangle { implicitHeight: 36; implicitWidth: 104; radius: 9; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.centerIn: parent; text: "Manual entry"; color: ws.text2; font.pixelSize: 12 } }
                            }
                            Text { text: ws.provider()+" · "+ws.filteredHosts.length+" entries"; color: ws.muted; font.pixelSize: 12 }
                            ListView {
                                id: lv; Layout.fillWidth: true; Layout.fillHeight: true; clip: true; model: ws.filteredHosts; spacing: 6
                                ScrollBar.vertical: ScrollBar { }
                                delegate: Rectangle {
                                    required property var modelData
                                    required property int index
                                    width: lv.width-4; implicitHeight: 62; radius: 11
                                    property bool sel: ws.selHost===modelData
                                    color: sel ? Qt.rgba(0.54,0.49,0.96,0.12) : (hh.hovered ? ws.panel2 : "transparent")
                                    border.color: sel ? ws.acc : "transparent"
                                    HoverHandler { id: hh }
                                    Rectangle { visible: sel; width: 3; height: parent.height-16; radius: 2; color: ws.acc; anchors.left: parent.left; anchors.leftMargin: 2; anchors.verticalCenter: parent.verticalCenter }
                                    RowLayout {
                                        anchors.fill: parent; anchors.leftMargin: 14; anchors.rightMargin: 12; spacing: 8
                                        Column { Layout.fillWidth: true; spacing: 3
                                            Text { text: modelData; color: ws.text; font.pixelSize: 13; font.bold: true; elide: Text.ElideRight; width: parent.width }
                                            Text { text: ("0000"+(index+6)).slice(-5)+" · "+(ws.curNet==="DMR"?"TG":"YSF")+" · "+(index%2?"international":"Greece"); color: ws.muted; font.pixelSize: 11 }
                                            Text { text: index===9 ? "Traffic detected" : "Activity unavailable"; color: index===9?ws.rxc:ws.muted; font.pixelSize: 11 } }
                                        Text { text: sel?"★":"☆"; color: sel?ws.acc2:ws.muted; font.pixelSize: 17 }
                                    }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ws.connected; onClicked: ws.selectHost(modelData) }
                                }
                            }
                            RowLayout { Layout.fillWidth: true
                                Text { text: "1–"+Math.min(100,ws.filteredHosts.length)+" / "+ws.filteredHosts.length; color: ws.muted; font.pixelSize: 11 }
                                Item { Layout.fillWidth: true }
                                Rectangle { implicitHeight: 28; implicitWidth: 78; radius: 8; color: "transparent"; border.color: ws.line2
                                    Text { anchors.centerIn: parent; text: "Previous"; color: ws.muted; font.pixelSize: 11 } }
                                Rectangle { implicitHeight: 28; implicitWidth: 56; radius: 8; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.centerIn: parent; text: "Next"; color: ws.text2; font.pixelSize: 11 } }
                            }
                        }
                    }

                    // ===== SELECTED =====
                    Rectangle {
                        Layout.fillHeight: true; Layout.fillWidth: true; Layout.preferredWidth: 40
                        radius: 14; color: ws.panel; border.color: ws.line
                        Flickable {
                            anchors.fill: parent; anchors.margins: 18; clip: true
                            contentHeight: selCol.implicitHeight
                            ColumnLayout {
                                id: selCol; width: parent.width; spacing: 0
                                Text { text: "Selected station"; color: ws.acc2; font.pixelSize: 12; font.bold: true; font.letterSpacing: 1 }
                                Text { text: ws.selHost===""?"Select a station":ws.selHost; color: ws.text; font.pixelSize: 21; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight; Layout.topMargin: 3 }
                                Text { text: ws.selHost===""?"Select an entry in the list on the left.":("00006 · "+(ws.curNet==="DMR"?"DMR":"YSF")); color: ws.muted; font.pixelSize: 12; Layout.topMargin: 2 }
                                Text { visible: ws.selHost!==""; text: "46.59.68.211 : 42000"; color: ws.muted; font.pixelSize: 12; Layout.topMargin: 2 }

                                // DMR TX-server box
                                Rectangle { visible: ws.curNet==="DMR"; Layout.fillWidth: true; Layout.topMargin: 12; implicitHeight: 86; radius: 11; color: ws.panel2; border.color: ws.line2
                                    ColumnLayout { anchors.fill: parent; anchors.margins: 12; spacing: 6
                                        Text { text: "Transmit server (TX)"; color: ws.muted; font.pixelSize: 11 }
                                        Text { text: "No server configured"; color: ws.text; font.pixelSize: 14; font.bold: true }
                                        Rectangle { implicitHeight: 28; implicitWidth: 150; radius: 8; color: "transparent"; border.color: ws.line2
                                            Text { anchors.centerIn: parent; text: "Choose DMR server"; color: ws.text2; font.pixelSize: 12 } } } }

                                // Module (D-Star)
                                Text { visible: ws.curNet==="D-Star"; text: "Module"; color: ws.muted; font.pixelSize: 11; Layout.topMargin: 12 }
                                Rectangle { visible: ws.curNet==="D-Star"; Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 38; radius: 9; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: _comboModule.currentText; color: ws.text; font.pixelSize: 13 }
                                    Text { anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: ws.muted; font.pixelSize: 14 }
                                    MouseArea { anchors.fill: parent; enabled: !ws.connected; cursorShape: Qt.PointingHandCursor; onClicked: { var n=_comboModule.currentIndex+1; if(n>=_comboModule.count) n=0; _comboModule.currentIndex=n } } }

                                Rectangle { Layout.topMargin: 12; implicitHeight: 32; implicitWidth: fav.width+24; radius: 8; color: ws.panel2; border.color: ws.line2
                                    Text { id: fav; anchors.centerIn: parent; text: (ws.selHost!=="" ? "★ Remove favourite" : "☆ Add favorite"); color: ws.text2; font.pixelSize: 12 } }

                                Text { text: "AUDIO"; color: ws.muted; font.pixelSize: 11; font.letterSpacing: 1; Layout.topMargin: 16 }
                                Text { text: "Microphone"; color: ws.text2; font.pixelSize: 11; Layout.topMargin: 8 }
                                Rectangle { Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 36; radius: 9; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: micch.left; anchors.verticalCenter: parent.verticalCenter; text: settingsTab.comboCapture.currentText; color: ws.text; font.pixelSize: 12; elide: Text.ElideRight }
                                    Text { id: micch; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: ws.muted; font.pixelSize: 14 }
                                    MouseArea { anchors.fill: parent; enabled: !ws.connected; cursorShape: Qt.PointingHandCursor; onClicked: { var n=settingsTab.comboCapture.currentIndex+1; if(n>=settingsTab.comboCapture.count) n=0; settingsTab.comboCapture.currentIndex=n } } }
                                Text { text: "Speakers"; color: ws.text2; font.pixelSize: 11; Layout.topMargin: 10 }
                                Rectangle { Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 36; radius: 9; color: ws.panel2; border.color: ws.line2
                                    Text { anchors.left: parent.left; anchors.leftMargin: 12; anchors.right: spkch.left; anchors.verticalCenter: parent.verticalCenter; text: settingsTab.comboPlayback.currentText; color: ws.text; font.pixelSize: 12; elide: Text.ElideRight }
                                    Text { id: spkch; anchors.right: parent.right; anchors.rightMargin: 12; anchors.verticalCenter: parent.verticalCenter; text: "⌄"; color: ws.muted; font.pixelSize: 14 }
                                    MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: { var n=settingsTab.comboPlayback.currentIndex+1; if(n>=settingsTab.comboPlayback.count) n=0; settingsTab.comboPlayback.currentIndex=n } } }
                                RowLayout { Layout.topMargin: 10; spacing: 8
                                    Repeater { model: ["Refresh devices","Test microphone","Test speakers"]
                                        delegate: Rectangle { required property var modelData; implicitHeight: 28; implicitWidth: dtt.width+18; radius: 8; color: ws.panel2; border.color: ws.line2
                                            Text { id: dtt; anchors.centerIn: parent; text: modelData; color: ws.text2; font.pixelSize: 11 } } } }
                                Text { text: settingsTab.comboCapture.count+" available microphones"; color: ws.muted; font.pixelSize: 11; Layout.topMargin: 8 }
                                Rectangle { Layout.fillWidth: true; Layout.topMargin: 6; implicitHeight: 4; radius: 2; color: ws.line }
                                RowLayout { Layout.fillWidth: true; Layout.topMargin: 12; spacing: 10
                                    Text { text: "RX volume"; color: ws.text2; font.pixelSize: 12 }
                                    Rectangle { Layout.fillWidth: true; implicitHeight: 6; radius: 3; color: ws.line2
                                        Rectangle { width: parent.width*0.82; height: parent.height; radius: 3; color: ws.acc
                                            Rectangle { width: 16; height: 16; radius: 8; color: ws.acc2; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter } } }
                                    Rectangle { width: 30; height: 30; radius: 8; color: ws.panel2; border.color: ws.line2
                                        Text { anchors.centerIn: parent; text: "♪"; color: ws.muted; font.pixelSize: 13 } } }

                                // Listen
                                RowLayout { Layout.fillWidth: true; Layout.topMargin: 18; spacing: 10
                                    Rectangle { implicitHeight: 40; implicitWidth: 112; radius: 10; color: ws.listening?Qt.rgba(0.25,0.72,0.91,0.16):ws.panel2; border.color: ws.listening?ws.cyan:ws.line2
                                        Row { anchors.centerIn: parent; spacing: 7
                                            Text { text: "🎧"; color: ws.listening?ws.cyan:ws.text2; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
                                            Text { text: ws.listening?"Listening":"Listen"; color: ws.listening?ws.cyan:ws.text; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter } }
                                        MouseArea { anchors.fill: parent; enabled: ws.selHost!==""; cursorShape: Qt.PointingHandCursor; onClicked: { if(!ws.connected) ws.doConnect(); ws.listening=true } } }
                                    Text { text: ws.listening?"Listening":"Listening stopped"; color: ws.muted; font.pixelSize: 12 }
                                }
                                // Connect (TX) + Stop all
                                RowLayout { Layout.fillWidth: true; Layout.topMargin: 10; spacing: 10
                                    Rectangle { Layout.fillWidth: true; implicitHeight: 46; radius: 11
                                        color: ws.connected ? ws.panel2 : (ws.selHost!=="" ? ws.acc : ws.panel2)
                                        border.color: ws.connected ? ws.acc : (ws.selHost!=="" ? "transparent" : ws.line2)
                                        Row { anchors.centerIn: parent; spacing: 8
                                            Text { text: "⏻"; color: ws.connected?ws.acc2:(ws.selHost!==""?"#0a0a14":ws.muted); font.pixelSize: 15; anchors.verticalCenter: parent.verticalCenter }
                                            Text { text: ws.connected?"Connected (TX)":(ws.connecting?"Connecting…":"Connect (TX)"); color: ws.connected?ws.acc2:(ws.selHost!==""?"#0a0a14":ws.muted); font.pixelSize: 14; font.bold: true; anchors.verticalCenter: parent.verticalCenter } }
                                        MouseArea { anchors.fill: parent; enabled: ws.selHost!==""&&!ws.connected; cursorShape: Qt.PointingHandCursor; onClicked: ws.doConnect() } }
                                    Rectangle { implicitHeight: 46; implicitWidth: 120; radius: 11; color: "transparent"; border.color: ws.danger
                                        Row { anchors.centerIn: parent; spacing: 7
                                            Text { text: "□"; color: ws.danger; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
                                            Text { text: "Stop all"; color: ws.danger; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter } }
                                        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ws.doStop() } }
                                }
                                // PTT
                                RowLayout { Layout.fillWidth: true; Layout.topMargin: 10; spacing: 10
                                    Rectangle { Layout.fillWidth: true; implicitHeight: 54; radius: 11; color: hold.pressed?Qt.rgba(1,0.67,0.26,0.2):ws.panel2; border.color: hold.pressed?ws.txc:ws.line2; opacity: ws.connected?1:0.5
                                        Row { anchors.centerIn: parent; spacing: 8
                                            Text { text: "🎙"; color: hold.pressed?ws.txc:ws.text2; font.pixelSize: 15; anchors.verticalCenter: parent.verticalCenter }
                                            Text { text: "Hold PTT"; color: hold.pressed?ws.txc:ws.text2; font.pixelSize: 14; font.bold: true; anchors.verticalCenter: parent.verticalCenter } }
                                        MouseArea { id: hold; anchors.fill: parent; enabled: ws.connected; onPressed: droidstar.press_tx(); onReleased: droidstar.release_tx(); onCanceled: droidstar.release_tx() } }
                                    Rectangle { Layout.fillWidth: true; implicitHeight: 54; radius: 11; color: ws.panel2; border.color: ws.line2; opacity: ws.connected?1:0.5
                                        Row { anchors.centerIn: parent; spacing: 8
                                            Text { text: "🔒"; color: ws.text2; font.pixelSize: 14; anchors.verticalCenter: parent.verticalCenter }
                                            Text { text: "Latch PTT"; color: ws.text2; font.pixelSize: 14; font.bold: true; anchors.verticalCenter: parent.verticalCenter } } }
                                }
                                RowLayout { Layout.fillWidth: true; Layout.topMargin: 12; spacing: 8
                                    Text { text: "Limit"; color: ws.muted; font.pixelSize: 12 }
                                    Rectangle { implicitHeight: 28; implicitWidth: 70; radius: 8; color: ws.panel2; border.color: ws.line2
                                        Text { anchors.centerIn: parent; text: "120 s ⌄"; color: ws.text2; font.pixelSize: 12 } }
                                    Item { Layout.fillWidth: true }
                                    Text { text: "02:00"; color: ws.text; font.pixelSize: 18; font.bold: true } }
                                Text { text: ws.connected?("TX · "+ws.curNet+" · 00006 · YSF"):(ws.selHost===""?"No TX destination":"Ready · "+ws.curNet); color: ws.connected?ws.rxc:ws.muted; font.pixelSize: 11; Layout.topMargin: 10 }
                                Item { Layout.preferredHeight: 6 }
                            }
                        }
                    }

                    // ===== LAST HEARD =====
                    Rectangle {
                        Layout.fillHeight: true; Layout.fillWidth: true; Layout.preferredWidth: 28
                        radius: 14; color: ws.panel; border.color: ws.line
                        ColumnLayout {
                            anchors.fill: parent; anchors.margins: 18; spacing: 0
                            Text { text: "Last station heard"; color: ws.text; font.pixelSize: 15; font.bold: true }
                            Item { Layout.fillWidth: true; Layout.preferredHeight: 170
                                Column { anchors.centerIn: parent; spacing: 12; width: parent.width
                                    Text { text: "🎧"; font.pixelSize: 40; color: ws.line2; anchors.horizontalCenter: parent.horizontalCenter }
                                    Text { text: "Station details will appear on reception."; color: ws.muted; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; width: 200; wrapMode: Text.WordWrap; anchors.horizontalCenter: parent.horizontalCenter } } }
                            Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: ws.line }
                            Text { text: "LAST HEARD"; color: ws.muted; font.pixelSize: 10; font.letterSpacing: 1; Layout.topMargin: 14 }
                            Text { text: "Waiting for data"; color: ws.muted; font.pixelSize: 12; Layout.topMargin: 6 }
                            Item { Layout.fillHeight: true }
                        }
                    }
                }

                // ===== AUDIO MIXER =====
                Rectangle {
                    Layout.fillWidth: true; implicitHeight: 128; color: ws.rail
                    ColumnLayout {
                        anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22; anchors.topMargin: 12; anchors.bottomMargin: 10; spacing: 8
                        RowLayout { Layout.fillWidth: true
                            Text { text: "Audio mixer"; color: ws.text; font.pixelSize: 13; font.bold: true }
                            Item { Layout.fillWidth: true }
                            Rectangle { radius: 8; color: ws.panel; border.color: ws.line2; implicitHeight: 30; implicitWidth: 240
                                Row { anchors.fill: parent; anchors.margins: 3
                                    Rectangle { width: 115; height: parent.height; radius: 6; color: "transparent"
                                        Text { anchors.centerIn: parent; text: "Single listening"; color: ws.muted; font.pixelSize: 11 } }
                                    Rectangle { width: 115; height: parent.height; radius: 6; color: Qt.rgba(0.54,0.49,0.96,0.18)
                                        Text { anchors.centerIn: parent; text: "Multiple listening"; color: ws.acc2; font.pixelSize: 11 } } } }
                            Rectangle { implicitHeight: 30; implicitWidth: 64; radius: 8; color: ws.panel; border.color: ws.line2
                                Text { anchors.centerIn: parent; text: "Hide ✕"; color: ws.muted; font.pixelSize: 11 } }
                        }
                        RowLayout { Layout.fillWidth: true; Layout.fillHeight: true; spacing: 12
                            Repeater { model: ws.nets
                                delegate: Rectangle { required property var modelData; Layout.fillWidth: true; Layout.fillHeight: true; radius: 10; color: ws.panel; border.color: ws.line
                                    RowLayout { anchors.fill: parent; anchors.margins: 12; spacing: 10
                                        Text { text: modelData.label; color: modelData.col; font.pixelSize: 12; font.bold: true }
                                        Text { text: modelData.label==="C4FM"?"RX volume":"Reception muted"; color: ws.muted; font.pixelSize: 11 }
                                        Rectangle { Layout.fillWidth: true; implicitHeight: 5; radius: 3; color: ws.line2
                                            Rectangle { width: parent.width*(modelData.label==="C4FM"?0.85:0.6); height: parent.height; radius: 3; color: modelData.col
                                                Rectangle { width: 12; height: 12; radius: 6; color: modelData.col; anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter } } }
                                        Rectangle { width: 26; height: 26; radius: 13; color: "transparent"; border.color: ws.line2
                                            Text { anchors.centerIn: parent; text: modelData.label==="C4FM"?"♪":"🔇"; color: ws.muted; font.pixelSize: 11 } } } }
                            }
                        }
                    }
                }

                // footer
                Rectangle { Layout.fillWidth: true; implicitHeight: 28; color: ws.bg
                    RowLayout { anchors.fill: parent; anchors.leftMargin: 22; anchors.rightMargin: 22
                        Text { text: "DIGICONNECT · HELLAS ZONE · Public activity depends on information available from each network."; color: ws.muted; font.pixelSize: 11 }
                        Item { Layout.fillWidth: true }
                        Text { text: "English ⌄"; color: ws.muted; font.pixelSize: 11 } }
                }
            }
        }
    }
}
