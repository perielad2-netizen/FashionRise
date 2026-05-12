using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Core.Navigation;
using FashionRise.Presentation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class SettingsScreen : ScreenBase
    {
        public override ScreenId Id => ScreenId.Settings;

        Text _autosaveLine = null!;
        InputField _intervalInput = null!;
        Text _authoringModeLine = null!;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Settings", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B",
                "Account and quality controls. Draft autosave runs in the background when you are signed in with API tokens.",
                t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal, TextAnchor.UpperCenter);

            FrUiFactory.AddLabel(col, "AsH", "Draft autosave", t, Mathf.RoundToInt(t.BodySize * 1.05f), FontStyle.Bold,
                TextAnchor.UpperLeft);
            _autosaveLine = FrUiFactory.AddLabel(col, "AsStat", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);
            FrUiFactory.AddButton(col, "Toggle autosave on/off", t, ToggleAutosave);
            FrUiFactory.AddLabel(col, "AsHint",
                $"Interval: {DesignAutosavePreferences.MinIntervalSeconds}–{DesignAutosavePreferences.MaxIntervalSeconds} seconds (default {DesignAutosavePreferences.DefaultIntervalSeconds}).",
                t, Mathf.RoundToInt(t.BodySize * 0.92f), FontStyle.Italic, TextAnchor.UpperLeft);
            _intervalInput = FrUiFactory.AddInputField(col, "IntervalSec", "seconds", t,
                Mathf.RoundToInt(t.BodySize));
            FrUiFactory.AddButton(col, "Apply interval", t, ApplyInterval);

            FrUiFactory.AddLabel(col, "ModeH", "Authoring mode", t, Mathf.RoundToInt(t.BodySize * 1.05f), FontStyle.Bold,
                TextAnchor.UpperLeft);
            _authoringModeLine = FrUiFactory.AddLabel(col, "ModeStat", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.UpperLeft);
            FrUiFactory.AddButton(col, "Toggle Guided / Pro mode", t, ToggleAuthoringMode);

            FrUiFactory.AddLabel(col, "AcctH", "Account", t, Mathf.RoundToInt(t.BodySize * 1.05f), FontStyle.Bold,
                TextAnchor.UpperLeft);
            FrUiFactory.AddButton(col, "Sign out", t, () => { _ = SignOutAsync(); }, FrButtonEmphasis.Destructive);

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload)
        {
            RefreshAutosaveUi();
            RefreshAuthoringModeUi();
        }

        void RefreshAutosaveUi()
        {
            var on = DesignAutosavePreferences.IsEnabled;
            var sec = DesignAutosavePreferences.GetIntervalSeconds();
            _autosaveLine.text = on
                ? $"Autosave is ON — every {sec} s."
                : "Autosave is OFF — use Save draft on Create design.";
            _intervalInput.text = sec.ToString();
        }

        void ToggleAutosave()
        {
            DesignAutosavePreferences.SetEnabled(!DesignAutosavePreferences.IsEnabled);
            RefreshAutosaveUi();
            var d = FindObjectOfType<DesignAutosaveDriver>();
            if (d != null)
                d.NotifyPreferencesChanged();
        }

        void RefreshAuthoringModeUi()
        {
            _authoringModeLine.text = AuthoringModePreferences.IsProMode
                ? "Pro mode is ON — advanced Create Design controls are visible."
                : "Guided mode is ON — Create Design shows essential controls only.";
        }

        void ToggleAuthoringMode()
        {
            AuthoringModePreferences.SetProMode(!AuthoringModePreferences.IsProMode);
            RefreshAuthoringModeUi();
        }

        void ApplyInterval()
        {
            if (!int.TryParse(_intervalInput.text?.Trim(), out var sec))
            {
                RefreshAutosaveUi();
                return;
            }

            DesignAutosavePreferences.SetIntervalSeconds(sec);
            RefreshAutosaveUi();
            var d = FindObjectOfType<DesignAutosaveDriver>();
            if (d != null)
                d.NotifyPreferencesChanged();
        }

        async Task SignOutAsync()
        {
            await App.Auth.SignOutAsync().ConfigureAwait(true);
            App.CreateDesign.Reset();
            if (App.Navigation != null)
                await App.Navigation.ResetToAsync(ScreenId.LoginChoice).ConfigureAwait(true);
        }
    }
}
