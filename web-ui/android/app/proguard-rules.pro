# FashionRise Android release — Capacitor + native plugins.
# Keep attributes needed for debugging / reflection-heavy Capacitor bridges.

-keepattributes SourceFile,LineNumberTable,*Annotation*,Signature,InnerClasses,EnclosingMethod
-renamesourcefileattribute SourceFile

# Capacitor core + plugins (JS bridge uses reflection).
-keep class com.getcapacitor.** { *; }
-keep class com.getcapacitor.plugin.** { *; }
-keepclassmembers class * {
    @com.getcapacitor.PluginMethod <methods>;
}
-keep @com.getcapacitor.annotation.CapacitorPlugin class * { *; }

# Cordova compatibility layer used by some Capacitor plugins.
-keep class org.apache.cordova.** { *; }

# FashionRise app entry.
-keep class app.fashionrise.studio.** { *; }

# Capgo Native Purchases / Billing Library.
-keep class ee.forgr.** { *; }
-keep class com.android.billingclient.** { *; }
-keep class com.android.vending.billing.** { *; }

# Firebase / FCM (when google-services.json is present).
-keep class com.google.firebase.** { *; }
-keep class com.google.android.gms.** { *; }
-dontwarn com.google.firebase.**
-dontwarn com.google.android.gms.**

# OkHttp / common AndroidX.
-dontwarn okhttp3.**
-dontwarn okio.**
-keep class okhttp3.** { *; }
-keep class okio.** { *; }
