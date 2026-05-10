using System.Threading.Tasks;
using FashionRise.Core.Navigation;
using FashionRise.UI;
using UnityEngine;
using UnityEngine.UI;

namespace FashionRise.Presentation.Screens
{
    public sealed class MaterialSelectionScreen : ScreenBase
    {
        RectTransform _list = null!;

        public override ScreenId Id => ScreenId.MaterialSelection;

        void Awake()
        {
            var t = ThemeOrDefault;
            var root = FrUiFactory.CreateStretchPanel(transform, "Root", t);
            var col = FrUiFactory.AddVerticalLayout(root, "Col", t.SectionGap, TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "H", "Materials", t, Mathf.RoundToInt(t.TitleSize), FontStyle.Bold,
                TextAnchor.UpperCenter);
            FrUiFactory.AddLabel(col, "B", "Data-driven catalog (mock seed).", t, Mathf.RoundToInt(t.BodySize),
                FontStyle.Normal, TextAnchor.UpperCenter);

            var listGo = new GameObject("List", typeof(RectTransform), typeof(VerticalLayoutGroup));
            _list = listGo.GetComponent<RectTransform>();
            _list.SetParent(col, false);
            var v = listGo.GetComponent<VerticalLayoutGroup>();
            v.spacing = t.ControlGap;
            v.childAlignment = TextAnchor.UpperCenter;
            v.childControlWidth = true;
            v.childForceExpandWidth = true;
            v.childControlHeight = true;
            v.childForceExpandHeight = false;
            var lrt = _list;
            lrt.sizeDelta = new Vector2(0, 400);

            FrUiFactory.AddButton(col, "Back", t, () =>
            {
                if (App.Navigation != null)
                    _ = App.Navigation.GoBackAsync();
            });
        }

        protected override void OnShown(object? payload) => _ = PopulateAsync();

        async Task PopulateAsync()
        {
            foreach (Transform c in _list)
                Destroy(c.gameObject);

            var mats = await App.Materials.GetMaterialsAsync().ConfigureAwait(true);
            var t = ThemeOrDefault;
            foreach (var m in mats)
            {
                var label = $"{m.DisplayName} — {m.FormalCasualTag}, luxury {m.LuxuryScore}/10";
                var id = m.Id;
                FrUiFactory.AddButton(_list, label, t, () =>
                {
                    App.CreateDesign.MaterialId = id;
                    if (App.Navigation != null)
                        _ = App.Navigation.GoBackAsync();
                });
            }
        }
    }
}
