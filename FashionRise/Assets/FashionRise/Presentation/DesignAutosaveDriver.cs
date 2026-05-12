using System.Threading.Tasks;
using FashionRise.Application;
using FashionRise.Core;
using UnityEngine;

namespace FashionRise.Presentation
{
    /// <summary>Periodic <see cref="Services.IDesignSaveService.SaveDraftAsync"/> while signed in (API tokens or mock user).</summary>
    public sealed class DesignAutosaveDriver : MonoBehaviour
    {
        AppServices _app = null!;
        float _nextDueUnscaled;
        bool _busy;

        public void Init(AppServices app)
        {
            _app = app;
            ScheduleNext();
        }

        /// <summary>Call after changing autosave prefs in Settings so the timer resets.</summary>
        public void NotifyPreferencesChanged() => ScheduleNext();

        void ScheduleNext()
        {
            if (!DesignAutosavePreferences.IsEnabled)
            {
                _nextDueUnscaled = float.PositiveInfinity;
                return;
            }

            _nextDueUnscaled = Time.unscaledTime + DesignAutosavePreferences.GetIntervalSeconds();
        }

        void Update()
        {
            if (_app == null || _busy)
                return;

            if (!DesignAutosavePreferences.IsEnabled)
            {
                _nextDueUnscaled = float.PositiveInfinity;
                return;
            }

            if (float.IsPositiveInfinity(_nextDueUnscaled))
                ScheduleNext();

            if (!MayAutosave())
                return;

            if (Time.unscaledTime < _nextDueUnscaled)
                return;

            _ = RunAutosaveAsync();
        }

        bool MayAutosave()
        {
            if (!_app.Auth.IsSignedIn)
                return false;
            if (_app.IsApiBackend)
                return _app.Auth.HasBackendSession;
            return true;
        }

        async Task RunAutosaveAsync()
        {
            _busy = true;
            try
            {
                var uid = _app.Auth.CurrentSessionUserId;
                if (string.IsNullOrEmpty(uid))
                    return;
                var d = _app.CreateDesign.ToDraft(uid, "Studio draft");
                d = await _app.DesignSave.SaveDraftAsync(d).ConfigureAwait(true);
                _app.CreateDesign.PersistedDesignId = d.Id;
            }
            catch (System.Exception ex)
            {
                Debug.LogWarning($"FashionRise: autosave draft failed ({ex.Message})");
            }
            finally
            {
                _busy = false;
                ScheduleNext();
            }
        }
    }
}
