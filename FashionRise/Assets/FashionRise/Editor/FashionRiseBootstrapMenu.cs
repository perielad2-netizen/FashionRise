#if UNITY_EDITOR
using FashionRise.Core;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace FashionRise.EditorTools
{
    public static class FashionRiseBootstrapMenu
    {
        const string MenuPath = "FashionRise/Create Bootstrap UI (Canvas + Screens)";

        [MenuItem(MenuPath)]
        static void CreateBootstrapUi()
        {
            var root = FashionRiseBootstrapBuilder.CreateUiRoot();
            Undo.RegisterCreatedObjectUndo(root, "Create FashionRise Bootstrap UI");
            Selection.activeGameObject = root;
        }

        /// <summary>
        /// One-click: point all <see cref="FashionRiseApp"/> in open scenes at local FastAPI and turn off mocks.
        /// Save the scene (Ctrl+S) so the next Play uses these values.
        /// </summary>
        [MenuItem("FashionRise/Use Local API (127.0.0.1:8001) — apply to scene")]
        static void ApplyLocalApiToScene()
        {
            var count = 0;
            foreach (var app in Object.FindObjectsOfType<FashionRiseApp>(true))
            {
                var so = new SerializedObject(app);
                var api = so.FindProperty("apiConfig");
                if (api == null)
                    continue;
                api.FindPropertyRelative("baseUrl")!.stringValue = "http://127.0.0.1:8001/api/v1";
                api.FindPropertyRelative("useMockServices")!.boolValue = false;
                api.FindPropertyRelative("useApiServices")!.boolValue = true;
                so.ApplyModifiedProperties();
                EditorUtility.SetDirty(app);
                if (!UnityEngine.Application.isPlaying && app.gameObject.scene.IsValid())
                    EditorSceneManager.MarkSceneDirty(app.gameObject.scene);
                count++;
            }

            if (count == 0)
            {
                EditorUtility.DisplayDialog(
                    "FashionRise",
                    "No FashionRiseApp found in open scenes.\n\n" +
                    "1) Use menu: FashionRise → Create Bootstrap UI (Canvas + Screens)\n" +
                    "2) Save the scene (Ctrl+S)\n" +
                    "3) Run this menu again, or select FashionRise_UI and edit Api Config manually.",
                    "OK");
                return;
            }

            Debug.Log($"FashionRise: applied local API settings to {count} FashionRiseApp instance(s). Save your scene (Ctrl+S).");
        }
    }
}
#endif
