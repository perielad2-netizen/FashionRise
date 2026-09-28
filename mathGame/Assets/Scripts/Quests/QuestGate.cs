using UnityEngine;

namespace MathGame.Quests
{
    public class QuestGate : MonoBehaviour
    {
        [SerializeField] QuestManager quests;
        [SerializeField] QuestAsset unlockQuest;
        [SerializeField] Collider2D[] blockers;
        [SerializeField] SpriteRenderer[] visuals;

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
            Refresh();
        }

        void Refresh()
        {
            if (quests == null || unlockQuest == null)
                return;

            bool open = quests.GetState(unlockQuest) == QuestState.Completed;
            if (blockers != null)
            {
                for (int i = 0; i < blockers.Length; i++)
                {
                    if (blockers[i] != null)
                        blockers[i].enabled = !open;
                }
            }

            if (visuals == null)
                return;

            for (int i = 0; i < visuals.Length; i++)
            {
                if (visuals[i] != null)
                    visuals[i].enabled = !open;
            }
        }
    }
}
