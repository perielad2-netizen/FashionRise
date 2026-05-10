package com.fashionrise.gallery;

import android.app.Activity;
import android.app.Fragment;
import android.content.ContentResolver;
import android.content.Intent;
import android.net.Uri;
import android.os.Bundle;
import com.unity3d.player.UnityPlayer;
import java.io.File;
import java.io.FileOutputStream;
import java.io.InputStream;
import java.io.IOException;

/**
 * Headless fragment + system image chooser. Copies selection into Unity persistent Imports dir.
 * Requires manifest &lt;queries&gt; for GET_CONTENT on API 30+ (see Plugins/Android/AndroidManifest.xml).
 */
public final class GalleryPick {
    private static String importsDir;
    private static final int REQ = 17331;
    private static final String BRIDGE = "FashionRiseAndroidBridge";

    public static void beginPick(String unityImportsDir) {
        importsDir = unityImportsDir;
        Activity a = UnityPlayer.currentActivity;
        if (a == null) {
            UnityPlayer.UnitySendMessage(BRIDGE, "OnGalleryPick", "");
            return;
        }
        PickerFragment frag = new PickerFragment();
        a.getFragmentManager().beginTransaction().add(frag, "FashionRiseGalleryPick").commitAllowingStateLoss();
    }

    public static class PickerFragment extends Fragment {
        @Override
        public void onCreate(Bundle savedInstanceState) {
            super.onCreate(savedInstanceState);
            Intent intent = new Intent(Intent.ACTION_GET_CONTENT);
            intent.setType("image/*");
            intent.addCategory(Intent.CATEGORY_OPENABLE);
            startActivityForResult(Intent.createChooser(intent, "Choose image"), REQ);
        }

        @Override
        public void onActivityResult(int requestCode, int resultCode, Intent data) {
            super.onActivityResult(requestCode, resultCode, data);
            Activity act = getActivity();
            try {
                if (act == null || requestCode != REQ || resultCode != Activity.RESULT_OK || data == null) {
                    UnityPlayer.UnitySendMessage(BRIDGE, "OnGalleryPick", "");
                    return;
                }
                Uri uri = data.getData();
                if (uri == null) {
                    UnityPlayer.UnitySendMessage(BRIDGE, "OnGalleryPick", "");
                    return;
                }
                ContentResolver cr = act.getContentResolver();
                InputStream in = cr.openInputStream(uri);
                if (in == null) {
                    UnityPlayer.UnitySendMessage(BRIDGE, "OnGalleryPick", "");
                    return;
                }
                File dir = new File(importsDir);
                dir.mkdirs();
                String name = "picked_" + System.currentTimeMillis() + ".jpg";
                File out = new File(dir, name);
                copyStream(in, new FileOutputStream(out));
                in.close();
                UnityPlayer.UnitySendMessage(BRIDGE, "OnGalleryPick", out.getAbsolutePath());
            } catch (Throwable e) {
                UnityPlayer.UnitySendMessage(BRIDGE, "OnGalleryPick", "");
            } finally {
                if (act != null) {
                    act.getFragmentManager().beginTransaction().remove(this).commitAllowingStateLoss();
                }
            }
        }

        static void copyStream(InputStream in, FileOutputStream out) throws IOException {
            byte[] buf = new byte[8192];
            int n;
            while ((n = in.read(buf)) > 0) {
                out.write(buf, 0, n);
            }
            out.flush();
            out.close();
        }
    }
}
