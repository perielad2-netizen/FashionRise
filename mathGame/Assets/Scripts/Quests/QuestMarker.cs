using UnityEngine;

namespace MathGame.Quests
{
    public class QuestMarker : MonoBehaviour
    {
        [SerializeField] QuestManager quests;
        [SerializeField] QuestAsset quest;
        [SerializeField] SpriteRenderer icon;
        [SerializeField] Sprite availableSprite;
        [SerializeField] Sprite activeSprite;

        void OnEnable()
        {
            if (quests != null)
                quests.QuestChanged += OnQuestChanged;

            Refresh();
        }

        void Start()
        {
            Refresh();
        }

        void OnDisable()
        {
            if (quests != null)
                quests.QuestChanged -= OnQuestChanged;
        }

        void OnQuestChanged(QuestAsset changed)
        {
            if (changed == null || quest == null || changed == quest || changed.Id == quest.Id)
                Refresh();
        }

        void Refresh()
        {
            if (icon == null || quests == null || quest == null)
                return;

            QuestState state = quests.GetState(quest);
            if (state == QuestState.Available && availableSprite != null)
            {
                icon.sprite = availableSprite;
                icon.enabled = true;
                return;
            }

            if (state == QuestState.Active && activeSprite != null)
            {
                icon.sprite = activeSprite;
                icon.enabled = true;
                return;
            }

            icon.enabled = false;
        }
    }
}
