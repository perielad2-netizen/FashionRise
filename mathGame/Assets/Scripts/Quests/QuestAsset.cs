using MathGame.Minigames;
using UnityEngine;

namespace MathGame.Quests
{
    [CreateAssetMenu(fileName = "Quest", menuName = "MathGame/Quest")]
    public class QuestAsset : ScriptableObject
    {
        [SerializeField] string id = "quest";
        [SerializeField] string title = "Quest";
        [SerializeField] string description = "";
        [SerializeField] string giverName = "";
        [SerializeField] MathChallenge challenge;
        [SerializeField] string rewardText = "";
        [SerializeField] string nextQuestId = "";

        public string Id => id;
        public string Title => title;
        public string Description => description;
        public string GiverName => giverName;
        public MathChallenge Challenge => challenge;
        public string RewardText => rewardText;
        public string NextQuestId => nextQuestId;
    }
}
