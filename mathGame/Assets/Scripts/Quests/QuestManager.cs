using System;
using System.Collections.Generic;
using UnityEngine;

namespace MathGame.Quests
{
    public class QuestManager : MonoBehaviour
    {
        [SerializeField] QuestAsset[] quests;
        [SerializeField] string startingAvailableQuestId = "quest-1";

        readonly Dictionary<string, QuestState> _states = new Dictionary<string, QuestState>();
        bool _ready;

        public event Action<QuestAsset> QuestChanged;

        void Awake()
        {
            EnsureReady();
        }

        public QuestState GetState(QuestAsset quest)
        {
            EnsureReady();
            if (quest == null || string.IsNullOrEmpty(quest.Id))
                return QuestState.Locked;

            QuestState state;
            return _states.TryGetValue(quest.Id, out state) ? state : QuestState.Locked;
        }

        public void MarkActive(QuestAsset quest)
        {
            EnsureReady();
            if (quest == null || !_states.ContainsKey(quest.Id))
                return;

            if (_states[quest.Id] == QuestState.Completed)
                return;

            _states[quest.Id] = QuestState.Active;
            QuestChanged?.Invoke(quest);
        }

        public void Complete(QuestAsset quest)
        {
            EnsureReady();
            if (quest == null || !_states.ContainsKey(quest.Id))
                return;

            _states[quest.Id] = QuestState.Completed;
            QuestChanged?.Invoke(quest);
            UnlockNext(quest.NextQuestId);
        }

        void UnlockNext(string nextQuestId)
        {
            if (string.IsNullOrEmpty(nextQuestId))
                return;

            QuestAsset next = Find(nextQuestId);
            if (next == null)
                return;

            QuestState state;
            if (!_states.TryGetValue(next.Id, out state) || state != QuestState.Locked)
                return;

            _states[next.Id] = QuestState.Available;
            QuestChanged?.Invoke(next);
        }

        QuestAsset Find(string id)
        {
            if (quests == null)
                return null;

            for (int i = 0; i < quests.Length; i++)
            {
                if (quests[i] != null && quests[i].Id == id)
                    return quests[i];
            }

            return null;
        }

        void EnsureReady()
        {
            if (_ready)
                return;

            _ready = true;
            if (quests == null)
                return;

            for (int i = 0; i < quests.Length; i++)
            {
                QuestAsset quest = quests[i];
                if (quest == null || string.IsNullOrEmpty(quest.Id))
                    continue;

                _states[quest.Id] = quest.Id == startingAvailableQuestId
                    ? QuestState.Available
                    : QuestState.Locked;
            }
        }
    }
}
