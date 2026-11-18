package app.fashionrise.studio;

import com.getcapacitor.BridgeActivity;

/**
 * Capacitor BridgeActivity hosts the WebView file chooser.
 *
 * Fitting Room camera uses HTML capture → BridgeWebChromeClient →
 * ACTION_IMAGE_CAPTURE. Do not re-add android.permission.CAMERA to the
 * app manifest; Capacitor treats an undefined CAMERA permission as
 * "media capture supported" and skips the FashionRise-owned runtime
 * permission dialog that crashed when dismissed with Back.
 */
public class MainActivity extends BridgeActivity {}
