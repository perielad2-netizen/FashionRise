using MathGame.Dialogue;
using MathGame.Minigames;
using UnityEngine;

namespace MathGame.Quests
{
    public class QuestGiver : MonoBehaviour
    {
        [SerializeField] QuestManager quests;
        [SerializeField] DialogueUI dialogue;
        [SerializeField] MathPanel mathPanel;
        [SerializeField] QuestAsset quest;
        [SerializeField] DialogueAsset introDialogue;
        [SerializeField] DialogueAsset lockedDialogue;
        [SerializeField] DialogueAsset activeDialogue;
        [SerializeField] DialogueAsset completedDialogue;

        public string HandleInteract()
        {
            if (quests == null || quest == null || dialogue == null)
                return null;

            switch (quests.GetState(quest))
            {
                case QuestState.Locked:
                    dialogue.Show(lockedDialogue != null ? lockedDialogue : introDialogue, null);
                    break;
                case QuestState.Available:
                    dialogue.Show(introDialogue, BeginAfterIntro);
                    break;
                case QuestState.Active:
                    ContinueActive();
                    break;
                case QuestState.Completed:
                    dialogue.Show(completedDialogue != null ? completedDialogue : introDialogue, null);
                    break;
            }

            return null;
        }

        void BeginAfterIntro()
        {
            quests.MarkActive(quest);
            OpenChallengeOrFinish();
        }

        void ContinueActive()
        {
            if (quest.Challenge != null && mathPanel != null)
            {
                OpenChallengeOrFinish();
                return;
            }

            dialogue.Show(activeDialogue != null ? activeDialogue : introDialogue, () => quests.Complete(quest));
        }

        void OpenChallengeOrFinish()
        {
            MathChallenge challenge = quest.Challenge;
            if (challenge == null || mathPanel == null)
            {
                quests.Complete(quest);
                return;
            }

            mathPanel.Open(challenge, quest.RewardText, () => quests.Complete(quest));
        }
    }
}
