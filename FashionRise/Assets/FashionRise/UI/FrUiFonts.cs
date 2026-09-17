using UnityEngine;

namespace FashionRise.UI
{
    /// <summary>
    /// Editorial type stack: Cormorant Garamond (display) + DM Sans (UI).
    /// Falls back to LegacyRuntime when Resources fonts are missing.
    /// </summary>
    public static class FrUiFonts
    {
        static Font? s_display;
        static Font? s_displayMedium;
        static Font? s_displayBold;
        static Font? s_ui;
        static Font? s_uiMedium;
        static Font? s_uiBold;
        static Font? s_legacy;

        static Font Legacy =>
            s_legacy != null
                ? s_legacy
                : (s_legacy = Resources.GetBuiltinResource<Font>("LegacyRuntime.ttf")!);

        public static Font Display =>
            s_display ??= Resources.Load<Font>("Fonts/CormorantGaramond-Regular") ?? Legacy;

        public static Font DisplayMedium =>
            s_displayMedium ??= Resources.Load<Font>("Fonts/CormorantGaramond-Medium") ?? Display;

        public static Font DisplayBold =>
            s_displayBold ??= Resources.Load<Font>("Fonts/CormorantGaramond-SemiBold")
                              ?? Resources.Load<Font>("Fonts/CormorantGaramond-Bold")
                              ?? DisplayMedium;

        public static Font Ui =>
            s_ui ??= Resources.Load<Font>("Fonts/DMSans-Regular") ?? Legacy;

        public static Font UiMedium =>
            s_uiMedium ??= Resources.Load<Font>("Fonts/DMSans-Medium")
                           ?? Resources.Load<Font>("Fonts/DMSans-SemiBold")
                           ?? Ui;

        public static Font UiBold =>
            s_uiBold ??= Resources.Load<Font>("Fonts/DMSans-Bold")
                         ?? Resources.Load<Font>("Fonts/DMSans-SemiBold")
                         ?? UiMedium;

        public static Font ForStyle(bool editorialTitle, FontStyle style)
        {
            if (editorialTitle)
            {
                return style == FontStyle.Bold || style == FontStyle.BoldAndItalic
                    ? DisplayBold
                    : Display;
            }

            return style == FontStyle.Bold || style == FontStyle.BoldAndItalic
                ? UiBold
                : style == FontStyle.Italic
                    ? UiMedium
                    : Ui;
        }
    }
}
