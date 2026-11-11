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

		readonly property color bg:    "#0a0e17"
		readonly property color bg2:   "#0d1320"
		readonly property color card:  "#131c2e"
		readonly property color card2: "#172134"
		readonly property color line:  "#1e2a3f"
		readonly property color line2: "#283750"
		readonly property color text:  "#e9eef6"
		readonly property color text2: "#aab7c9"
		readonly property color muted: "#6f7f95"
		readonly property color acc:   "#4da3ff"
		readonly property color acc2:  "#7c9bff"
		readonly property color rxc:   "#37d98a"
		readonly property color txc:   "#ffab42"
		readonly property color pink:  "#ff6fae"

		property string curNet: "C4FM"
		property string selHost: ""
		property string search: ""
		property bool   listening: false
		property bool   connected: (_connectbutton.text === "Disconnect")
		property bool   connecting: (_connectbutton.text === "Connecting")

		property var nets: [
			{label:"DMR",      mode:"DMR", col:"#8b7bff"},
			{label:"D-Star",   mode:"REF", col:"#ffb02e"},
			{label:"EchoLink", mode:"IAX", col:"#35c6ff"},
			{label:"C4FM",     mode:"YSF", col:"#ff6fae"}
		]
		function netCol(n){ for(var i=0;i<nets.length;i++) if(nets[i].label===n) return nets[i].col; return acc }
		function netMode(n){ for(var i=0;i<nets.length;i++) if(nets[i].label===n) return nets[i].mode; return "YSF" }
		function labelForMode(m){ for(var i=0;i<nets.length;i++) if(nets[i].mode===m) return nets[i].label; return m }

		// host list taken from the real (engine-populated) _comboHost model
		property var filteredHosts: {
			var _n = _comboHost.count;            // reactive trigger on repopulation
			var _m = _comboMode.currentText;      // reactive trigger on mode change
			var q = ws.search.toLowerCase();
			var src = _comboHost.model;
			var a = [];
			if(src){
				for(var i=0;i<src.length;i++){
					var t = String(src[i]);
					if(q==="" || t.toLowerCase().indexOf(q)>=0) a.push(t);
				}
			}
			return a;
		}

		function selectMode(mode, label){
			ws.curNet = label;
			ws.selHost = "";
			ws.search = "";
			_comboMode.loaded = true;
			var ix = _comboMode.find(mode);
			if(ix>=0) _comboMode.currentIndex = ix;
		}
		function selectHost(h){
			ws.selHost = h;
			var ix = _comboHost.find(h);
			if(ix>=0) _comboHost.currentIndex = ix;
		}

		// live clock
		property string clockUtc: ""
		property string clockLocal: ""
		function pad(n){ return (n<10?"0":"")+n }
		function tick(){
			var d = new Date();
			ws.clockUtc = pad(d.getUTCHours())+":"+pad(d.getUTCMinutes())+":"+pad(d.getUTCSeconds())+" UTC";
			ws.clockLocal = pad(d.getHours())+":"+pad(d.getMinutes())+":"+pad(d.getSeconds())+" local";
		}
		Timer { interval: 1000; running: true; repeat: true; triggeredOnStart: true; onTriggered: ws.tick() }

		Component.onCompleted: {
			ws.tick();
			_comboMode.loaded = true;
			var ix = _comboMode.find(ws.netMode(ws.curNet));
			if(ix>=0) _comboMode.currentIndex = ix;
		}

		RowLayout {
			anchors.fill: parent
			spacing: 0

			// ============ LEFT RAIL ============
			Rectangle {
				Layout.preferredWidth: 54
				Layout.fillHeight: true
				color: ws.bg2
				ColumnLayout {
					anchors.fill: parent
					anchors.topMargin: 10
					anchors.bottomMargin: 10
					spacing: 4
					Rectangle {
						Layout.alignment: Qt.AlignHCenter
						width: 34; height: 34; radius: 9
						gradient: Gradient {
							GradientStop { position: 0; color: ws.acc }
							GradientStop { position: 1; color: ws.acc2 }
						}
					}
					Repeater {
						model: ["▦","✚","☰","▤","◷","🎧"]
						delegate: Rectangle {
							required property var modelData
							required property int index
							Layout.alignment: Qt.AlignHCenter
							width: 36; height: 36; radius: 9
							color: index===0 ? Qt.rgba(0.3,0.64,1,0.14) : "transparent"
							Text { anchors.centerIn: parent; text: modelData; color: index===0?ws.acc:ws.muted; font.pixelSize: 15 }
						}
					}
					Item { Layout.fillHeight: true }
					Rectangle {
						Layout.alignment: Qt.AlignHCenter
						width: 32; height: 32; radius: 16; color: ws.card2; border.color: ws.line2
						Text { anchors.centerIn: parent; text: "SA"; color: ws.text; font.pixelSize: 11; font.bold: true }
					}
				}
			}

			// ============ MAIN ============
			ColumnLayout {
				Layout.fillWidth: true
				Layout.fillHeight: true
				spacing: 0

				// ---- top bar ----
				Rectangle {
					Layout.fillWidth: true
					implicitHeight: 52
					color: ws.bg2
					RowLayout {
						anchors.fill: parent
						anchors.leftMargin: 16; anchors.rightMargin: 16
						spacing: 10
						Image {
							source: "images/droidstar.png"
							Layout.alignment: Qt.AlignVCenter
							sourceSize.height: 34; sourceSize.width: 34
							fillMode: Image.PreserveAspectFit
							smooth: true
						}
						Column {
							Layout.alignment: Qt.AlignVCenter
							Text { text: "HELLAS ZONE"; color: ws.muted; font.pixelSize: 9; font.letterSpacing: 2 }
							Text { text: "DIGI<font color='"+ws.acc+"'>CONNECT</font>"; textFormat: Text.RichText; color: ws.text; font.pixelSize: 16; font.bold: true }
						}
						Item { Layout.fillWidth: true }
						Column {
							Layout.alignment: Qt.AlignVCenter
							Text { text: ws.clockUtc; color: ws.text; font.pixelSize: 13; font.bold: true; horizontalAlignment: Text.AlignRight; width: 96 }
							Text { text: ws.clockLocal; color: ws.muted; font.pixelSize: 10; horizontalAlignment: Text.AlignRight; width: 96 }
						}
						Text { text: (settingsTab.callsignEdit.text==="" ? "NOCALL" : settingsTab.callsignEdit.text); color: ws.acc; font.pixelSize: 13; font.bold: true }
					}
				}

				// ---- workspace header ----
				Item {
					Layout.fillWidth: true
					implicitHeight: 62
					RowLayout {
						anchors.fill: parent
						anchors.leftMargin: 18; anchors.rightMargin: 18
						spacing: 10
						Column {
							Layout.alignment: Qt.AlignVCenter
							Text { text: "Radio workspace <font color='"+ws.netCol(ws.curNet)+"'>"+ws.curNet+"</font>"; textFormat: Text.RichText; color: ws.text; font.pixelSize: 21; font.bold: true }
							Text { text: "Choose a station, then Connect. PTT transmits once connected."; color: ws.muted; font.pixelSize: 12 }
						}
						Item { Layout.fillWidth: true }
						Rectangle { implicitHeight: 30; implicitWidth: 112; radius: 8; color: ws.card; border.color: ws.line2
							Text { anchors.centerIn: parent; text: "↻ Refresh hosts"; color: ws.text; font.pixelSize: 12 }
							MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
								onClicked: { _comboMode.loaded = true; droidstar.process_mode_change(_comboMode.currentText) } } }
					}
				}

				// ---- network tabs ----
				Flow {
					Layout.fillWidth: true
					Layout.leftMargin: 18; Layout.rightMargin: 18; Layout.bottomMargin: 10
					spacing: 7
					Repeater {
						model: ws.nets
						delegate: Rectangle {
							required property var modelData
							implicitHeight: 34; implicitWidth: tabRow.implicitWidth+24; radius: 9
							property bool on: ws.curNet===modelData.label
							color: on ? Qt.rgba(0.3,0.64,1,0.14) : ws.card
							border.color: on ? ws.acc : ws.line2
							Row {
								id: tabRow; anchors.centerIn: parent; spacing: 8
								Rectangle { width: 8; height: 8; radius: 4; color: modelData.col; anchors.verticalCenter: parent.verticalCenter }
								Text { text: modelData.label; color: on ? ws.text : ws.text2; font.pixelSize: 13; font.bold: true; anchors.verticalCenter: parent.verticalCenter }
							}
							MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ws.connected && !ws.connecting
								onClicked: ws.selectMode(modelData.mode, modelData.label) }
						}
					}
				}
				Rectangle { Layout.fillWidth: true; implicitHeight: 1; color: ws.line }

				// ---- 3 columns ----
				RowLayout {
					Layout.fillWidth: true
					Layout.fillHeight: true
					spacing: 0

					// ===== DIRECTORY =====
					ColumnLayout {
						Layout.fillHeight: true
						Layout.fillWidth: true
						Layout.preferredWidth: 5
						spacing: 0
						RowLayout {
							Layout.fillWidth: true; Layout.margins: 12; spacing: 8
							Text { text: "Station directory"; color: ws.text; font.pixelSize: 13; font.bold: true }
							Item { Layout.fillWidth: true }
							Rectangle { implicitHeight: 28; implicitWidth: 64; radius: 8; color: ws.card; border.color: ws.line2
								Text { anchors.centerIn: parent; text: "Refresh"; color: ws.text2; font.pixelSize: 12 }
								MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
									onClicked: { _comboMode.loaded = true; droidstar.process_mode_change(_comboMode.currentText) } } }
						}
						Rectangle {
							Layout.fillWidth: true; Layout.leftMargin: 12; Layout.rightMargin: 12; implicitHeight: 36; radius: 9; color: ws.card; border.color: ws.line2
							Row {
								anchors.fill: parent; anchors.leftMargin: 10; spacing: 8
								Text { text: "🔍"; color: ws.muted; font.pixelSize: 13; anchors.verticalCenter: parent.verticalCenter }
								TextInput {
									id: searchIn
									width: parent.width - 40; anchors.verticalCenter: parent.verticalCenter
									color: ws.text; font.pixelSize: 12; clip: true
									onTextChanged: ws.search = text
									Text { visible: searchIn.text===""; text: "Search host, TG or reflector…"; color: ws.muted; font.pixelSize: 12; anchors.verticalCenter: parent.verticalCenter }
								}
							}
						}
						Text { Layout.leftMargin: 14; Layout.topMargin: 8; Layout.bottomMargin: 4; text: ws.curNet+" · "+ws.filteredHosts.length+" entries"; color: ws.muted; font.pixelSize: 12 }
						ListView {
							id: lv
							Layout.fillWidth: true; Layout.fillHeight: true; Layout.leftMargin: 8; Layout.rightMargin: 8
							clip: true; model: ws.filteredHosts; spacing: 4
							ScrollBar.vertical: ScrollBar { }
							delegate: Rectangle {
								required property var modelData
								required property int index
								width: lv.width - 4; implicitHeight: 48; radius: 10
								property bool sel: ws.selHost===modelData
								color: sel ? Qt.rgba(1,0.44,0.68,0.12) : (hov.hovered ? ws.card : "transparent")
								border.color: sel ? ws.pink : "transparent"
								HoverHandler { id: hov }
								RowLayout {
									anchors.fill: parent; anchors.leftMargin: 12; anchors.rightMargin: 10; spacing: 8
									Column {
										Layout.fillWidth: true; spacing: 2
										Text { text: modelData; color: ws.text; font.pixelSize: 13; font.bold: true; elide: Text.ElideRight; width: parent.width }
										Text { text: ws.curNet+" reflector"; color: ws.muted; font.pixelSize: 11 }
									}
									Text { text: sel ? "★" : "☆"; color: sel ? ws.pink : ws.muted; font.pixelSize: 16 }
								}
								MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; enabled: !ws.connected
									onClicked: ws.selectHost(modelData) }
							}
						}
						Text { Layout.leftMargin: 14; Layout.topMargin: 4; Layout.bottomMargin: 8; text: ws.filteredHosts.length+" shown"; color: ws.muted; font.pixelSize: 11 }
					}

					Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: ws.line }

					// ===== SELECTED =====
					Rectangle {
						Layout.fillHeight: true; Layout.preferredWidth: 360; color: ws.bg
						ColumnLayout {
							anchors.fill: parent; anchors.margins: 16; spacing: 0
							Text { text: "SELECTED STATION"; color: ws.muted; font.pixelSize: 11; font.letterSpacing: 1 }
							Text { text: ws.selHost===""?"Select a station":ws.selHost; color: ws.text; font.pixelSize: 19; font.bold: true; Layout.fillWidth: true; elide: Text.ElideRight; Layout.topMargin: 2 }
							Text { text: ws.selHost===""?"Pick an entry in the list on the left.":ws.curNet+" · reflector"; color: ws.muted; font.pixelSize: 12; Layout.bottomMargin: 10 }

							// Module (REF/D-Star) — drives the real _comboModule
							Text { text: "MODULE"; color: ws.muted; font.pixelSize: 11; font.letterSpacing: 1; Layout.topMargin: 6; visible: _comboModule.visible }
							Rectangle { Layout.fillWidth: true; Layout.topMargin: 4; implicitHeight: 34; radius: 9; color: ws.card; border.color: ws.line2; visible: _comboModule.visible
								Text { anchors.left: parent.left; anchors.leftMargin: 10; anchors.verticalCenter: parent.verticalCenter; text: "Module "+_comboModule.currentText; color: ws.text2; font.pixelSize: 12 }
								Text { anchors.right: parent.right; anchors.rightMargin: 10; anchors.verticalCenter: parent.verticalCenter; text: "‹ ›"; color: ws.muted; font.pixelSize: 14 }
								MouseArea { anchors.fill: parent; enabled: !ws.connected; cursorShape: Qt.PointingHandCursor
									onClicked: { var n=_comboModule.currentIndex+1; if(n>=_comboModule.count) n=0; _comboModule.currentIndex=n } } }

							// RX volume -> real sliderMicGain stays in Settings; here a visual level
							Text { text: "AUDIO"; color: ws.muted; font.pixelSize: 11; font.letterSpacing: 1; Layout.topMargin: 10 }
							Text { text: "Microphone and speaker devices are chosen in Settings."; color: ws.muted; font.pixelSize: 11; Layout.topMargin: 4; Layout.fillWidth: true; wrapMode: Text.WordWrap }

							// Connect / Disconnect -> drives the real connect button
							Rectangle {
								Layout.fillWidth: true; Layout.topMargin: 16; implicitHeight: 42; radius: 9
								color: ws.connected ? "#ff5a6e" : (ws.connecting ? ws.card2 : (ws.selHost!==""?ws.acc:ws.card))
								border.color: (ws.selHost!=="" || ws.connected) ? "transparent" : ws.line2
								Text { anchors.centerIn: parent
									text: ws.connected ? "⏼ Disconnect" : (ws.connecting ? "Connecting…" : "⏼ Connect")
									color: ws.connected?"#fff":(ws.connecting?ws.text2:(ws.selHost!==""?"#06121f":ws.muted)); font.pixelSize: 14; font.bold: true }
								MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
									enabled: ws.connected || ws.selHost!==""
									onClicked: _connectbutton.clicked() }
							}

							// PTT
							RowLayout {
								Layout.fillWidth: true; Layout.topMargin: 8; spacing: 8
								Rectangle {
									Layout.fillWidth: true; implicitHeight: 50; radius: 10
									color: holdMa.pressed ? Qt.rgba(1,0.67,0.26,0.2) : ws.card2
									border.color: holdMa.pressed ? ws.txc : ws.line2
									opacity: ws.connected ? 1 : 0.45
									Text { anchors.centerIn: parent; text: "🎙 Hold to talk"; color: holdMa.pressed?ws.txc:ws.text2; font.pixelSize: 14; font.bold: true }
									MouseArea { id: holdMa; anchors.fill: parent; enabled: ws.connected
										onPressed: droidstar.press_tx(); onReleased: droidstar.release_tx(); onCanceled: droidstar.release_tx() }
								}
							}
							Text { text: "Connect opens the reflector link. Hold to talk keys the transmitter while pressed."; color: ws.muted; font.pixelSize: 11; Layout.fillWidth: true; Layout.topMargin: 12; wrapMode: Text.WordWrap }
							Text { text: _netstatus.text===""?"Not connected":_netstatus.text; color: ws.connected?ws.rxc:ws.muted; font.pixelSize: 12; font.bold: true; Layout.topMargin: 10 }
							Text { text: _ambestatus.text; color: ws.muted; font.pixelSize: 11; Layout.topMargin: 2; visible: _ambestatus.text!=="" }
							Item { Layout.fillHeight: true }
						}
					}

					Rectangle { Layout.fillHeight: true; implicitWidth: 1; color: ws.line }

					// ===== LAST HEARD =====
					Rectangle {
						Layout.fillHeight: true; Layout.preferredWidth: 260; color: ws.bg
						ColumnLayout {
							anchors.fill: parent; anchors.margins: 16; spacing: 0
							Text { text: "Last station heard"; color: ws.text; font.pixelSize: 14; font.bold: true }
							property bool haveRx: _data1.text!=="" || _data2.text!==""
							Item {
								Layout.fillWidth: true; Layout.preferredHeight: 140
								visible: !parent.haveRx
								Column {
									anchors.centerIn: parent; spacing: 10; width: parent.width
									Text { text: "🎧"; font.pixelSize: 34; color: ws.muted; anchors.horizontalCenter: parent.horizontalCenter }
									Text { text: "Station details appear here on reception."; color: ws.muted; font.pixelSize: 12; horizontalAlignment: Text.AlignHCenter; width: 200; wrapMode: Text.WordWrap; anchors.horizontalCenter: parent.horizontalCenter }
								}
							}
							Column {
								Layout.fillWidth: true; Layout.topMargin: 10; spacing: 6
								visible: parent.haveRx
								Text { text: _data1.text; color: ws.rxc; font.pixelSize: 18; font.bold: true }
								Text { text: _data2.text; color: ws.text2; font.pixelSize: 12 }
								Text { text: _data3.text; color: ws.muted; font.pixelSize: 11 }
								Text { text: _data4.text; color: ws.muted; font.pixelSize: 11 }
								Text { text: _data5.text; color: ws.muted; font.pixelSize: 11 }
							}
							Item { Layout.fillHeight: true }
						}
					}
				}
			}
		}
	}
}
