package app.fashionrise.studio;

import android.os.Bundle;

import androidx.activity.EdgeToEdge;
import androidx.core.graphics.Insets;
import androidx.core.view.ViewCompat;
import androidx.core.view.WindowInsetsCompat;

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
 * Android 15+: enable edge-to-edge via androidx EdgeToEdge (avoids deprecated
 * Window status/navigation bar color APIs) and apply system bar insets to the
 * content root so the WebView is not drawn under the status/nav bars.
 */
public class MainActivity extends BridgeActivity {
    @Override
    public void onCreate(Bundle savedInstanceState) {
        EdgeToEdge.enable(this);
        super.onCreate(savedInstanceState);
        ViewCompat.setOnApplyWindowInsetsListener(findViewById(android.R.id.content), (v, insets) -> {
            Insets bars = insets.getInsets(WindowInsetsCompat.Type.systemBars());
            v.setPadding(bars.left, bars.top, bars.right, bars.bottom);
            return insets;
        });
    }
}
