using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class LoginChoiceScreen : ScreenBase
    {
        Text _status = null!;
        RectTransform _layoutCol = null!;
        InputField? _email;
        InputField? _password;
        InputField? _username;
        bool _apiFieldsBuilt;
        Button? _mockSignInButton;

        public override ScreenId Id => ScreenId.LoginChoice;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            _layoutCol = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.MiddleCenter);
            FrUiFactory.AddBrandLogoRow(_layoutCol, t, 220f, 72f);
            FrUiFactory.AddLabel(_layoutCol, "H", "Sign in", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.MiddleCenter);

            _status = FrUiFactory.AddLabel(_layoutCol, "St", "", t, Mathf.RoundToInt(t.BodySize), FontStyle.Normal,
                TextAnchor.MiddleCenter, useSecondaryTextColor: true);
            var statusLe = _status.gameObject.AddComponent<LayoutElement>();
            statusLe.minHeight = 96f;
            statusLe.preferredHeight = 140f;
            _status.verticalOverflow = VerticalWrapMode.Overflow;

            _mockSignInButton = FrUiFactory.AddButton(_layoutCol, "Sign in (mock)", t, async () =>
            {
                ClearStatus();
                if (App.IsApiBackend)
                {
                    ShowResult("Use email/password fields for API sign-in.");
                    return;
                }

                await App.Auth.SignInAsync("creator@fashionrise.app", "mock").ConfigureAwait(true);
                if (App.Navigation != null)
                    await App.Navigation.NavigateToAsync(ScreenId.HomeDashboard).ConfigureAwait(true);
            }, FrButtonEmphasis.Primary);
        }

        protected override void OnShown(object? payload)
        {
            if (_apiFieldsBuilt || !App.IsApiBackend)
                return;

            if (_mockSignInButton != null)
                _mockSignInButton.gameObject.SetActive(false);

            var t = ThemeOrDefault;
            _status.text =
                "API sign-in / register:\n" +
                "• Email must look like name@domain.com\n" +
                "• Username: 2+ characters\n" +
                "• Password: 8+ characters";
            _email = FrUiFactory.AddInputField(_layoutCol, "Email", "email", t, Mathf.RoundToInt(t.BodySize));
            _password = FrUiFactory.AddInputField(_layoutCol, "Password", "password", t, Mathf.RoundToInt(t.BodySize));
            _username = FrUiFactory.AddInputField(_layoutCol, "Username (register)", "username", t,
                Mathf.RoundToInt(t.BodySize));

            FrUiFactory.AddButton(_layoutCol, "Sign in (API)", t, async () => { await ApiSignInAsync().ConfigureAwait(true); },
                FrButtonEmphasis.Primary);
            FrUiFactory.AddButton(_layoutCol, "Register (API)", t, async () => { await ApiRegisterAsync().ConfigureAwait(true); });
            _apiFieldsBuilt = true;
        }

        async System.Threading.Tasks.Task ApiSignInAsync()
        {
            ClearStatus();
            if (_email == null || _password == null)
                return;
            var email = _email.text.Trim();
            if (string.IsNullOrEmpty(email) || !email.Contains('@'))
            {
                ShowResult("Enter your email (must include @).");
                return;
            }

            if (string.IsNullOrEmpty(_password.text))
            {
                ShowResult("Enter your password.");
                return;
            }

            var r = await App.Auth.SignInAsync(email, _password.text.Trim()).ConfigureAwait(true);
            ShowResult(r.Message);
            if (r.Success && App.Navigation != null)
                await App.Navigation.NavigateToAsync(ScreenId.HomeDashboard).ConfigureAwait(true);
        }

        async System.Threading.Tasks.Task ApiRegisterAsync()
        {
            ClearStatus();
            if (_email == null || _password == null || _username == null)
                return;
            var email = _email.text.Trim();
            var username = _username.text.Trim();
            var password = _password.text.Trim();
            if (!TryValidateRegister(email, username, password, out var err))
            {
                ShowResult(err);
                return;
            }

            var r = await App.Auth.RegisterAsync(email, username, password, displayName: username)
                .ConfigureAwait(true);
            ShowResult(r.Message);
            if (r.Success && App.Navigation != null)
                await App.Navigation.NavigateToAsync(ScreenId.HomeDashboard).ConfigureAwait(true);
        }

        static bool TryValidateRegister(string email, string username, string password, out string error)
        {
            error = "";
            if (string.IsNullOrEmpty(email) || !email.Contains('@'))
            {
                error = "Email must include @ (e.g. you@example.com).";
                return false;
            }

            if (username.Length < 2)
            {
                error = "Username must be at least 2 characters.";
                return false;
            }

            if (password == null || password.Length < 8)
            {
                error = "Password must be at least 8 characters.";
                return false;
            }

            return true;
        }

        void ClearStatus() => _status.text = "";

        void ShowResult(string msg)
        {
            if (string.IsNullOrEmpty(msg))
                return;
            const int maxLen = 600;
            _status.text = msg.Length > maxLen ? msg.Substring(0, maxLen) + "…" : msg;
        }
    }
}
