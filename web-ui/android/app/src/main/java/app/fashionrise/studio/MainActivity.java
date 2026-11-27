package app.fashionrise.studio;

import android.os.Bundle;

import com.getcapacitor.BridgeActivity;

/**
 * Capacitor BridgeActivity hosts the WebView file chooser.
 *
 * Fitting Room camera uses HTML capture → BridgeWebChromeClient →
 * ACTION_IMAGE_CAPTURE. Do not re-add android.permission.CAMERA to the
 * app manifest; Capacitor treats an undefined CAMERA permission as
 * "media capture supported" and skips the FashionRise-owned runtime
 * permission dialog that crashed when dismissed with Back.
 *
 * Do not call EdgeToEdge.enable() or pad {@code android.R.id.content} with
 * system-bar insets here. Capacitor StatusBar overlays the WebView and the
 * React shell already applies {@code env(safe-area-inset-*)} once. Native
 * padding (PR #526) double-applied insets and surfaced a blank strip plus
 * ActionBar/theme regressions on device.
 */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        registerPlugin(NotificationSettingsPlugin.class);
        super.onCreate(savedInstanceState);
    }
}
