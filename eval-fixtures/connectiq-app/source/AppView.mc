using Toybox.WatchUi;
using Toybox.Graphics;
using Toybox.Communications;

class AppView extends WatchUi.View {
    hidden var mData;

    function initialize() {
        View.initialize();
        mData = {};
    }

    function onUpdate(dc) {
        dc.clear();
        var power = mData["power"];
        dc.drawText(10, 10, Graphics.FONT_MEDIUM, power.toString(), Graphics.TEXT_JUSTIFY_LEFT);
    }

    function fetch() {
        Communications.makeWebRequest(
            "https://api.example.com/latest",
            {},
            {},
            method(:onReceive)
        );
    }

    function onReceive(responseCode, data) {
        mData = data;
        WatchUi.requestUpdate();
    }
}
