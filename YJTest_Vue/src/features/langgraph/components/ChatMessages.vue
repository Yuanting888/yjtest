<template>
  <div class="chat-messages" ref="messagesContainer">
    <div v-if="messages.length === 0" class="empty-chat">
      <div class="empty-icon">
        <img :src="brandLogoUrl" alt="" class="empty-logo" />
      </div>
      <p>{{ brandChatEmptyCopy }}</p>
    </div>

    <MessageItem
      v-for="(message, index) in messages"
      :key="index"
      :message="message"
      :floating-tool-image-src="floatingToolImageSrc"
      @toggle-expand="$emit('toggle-expand', $event)"
      @quote="$emit('quote', $event)"
      @retry="$emit('retry', $event)"
      @delete="$emit('delete', $event)"
      @preview-diagram="$emit('preview-diagram', $event)"
      @preview-html="$emit('preview-html', $event)"
      @tool-image-detected="$emit('tool-image-detected', $event)"
      @float-tool-image="$emit('float-tool-image', $event)"
    />
  </div>
</template>

<script setup lang="ts">
import { nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import { brandChatEmptyCopy } from '@/config/brand';
import type { ToolFileAttachment } from '@/features/langgraph/utils/toolResultParser';
import { brandLogoUrl } from '@/utils/assetUrl';
import MessageItem from './MessageItem.vue';

interface ChatMessage {
  content: string;
  isUser: boolean;
  time: string;
  isLoading?: boolean;
  messageType?: 'human' | 'ai' | 'tool' | 'system' | 'agent_step' | 'step_separator';
  toolName?: string;
  isExpanded?: boolean;
  isStreaming?: boolean;
  imageBase64?: string;
  imageDataUrl?: string;
  fileAttachments?: ToolFileAttachment[];
  imageBase64List?: string[];
  imageDataUrls?: string[];
  isThinkingProcess?: boolean;
  isThinkingExpanded?: boolean;
  stepNumber?: number;
  maxSteps?: number;
  stepStatus?: 'start' | 'complete' | 'error';
  isStepSeparator?: boolean;
}

interface Props {
  messages: ChatMessage[];
  isLoading: boolean;
  floatingToolImageSrc?: string | null;
}

const props = withDefaults(defineProps<Props>(), {
  floatingToolImageSrc: null,
});

defineEmits<{
  'toggle-expand': [message: ChatMessage];
  quote: [message: ChatMessage];
  retry: [message: ChatMessage];
  delete: [message: ChatMessage];
  'preview-diagram': [payload: { xml: string; sourceMessage: ChatMessage }];
  'preview-html': [payload: { html: string; sourceMessage: ChatMessage }];
  'tool-image-detected': [src: string];
  'float-tool-image': [src: string];
}>();

const messagesContainer = ref<HTMLElement | null>(null);
const userIsScrolling = ref(false);
let scrollTimeout: number | null = null;

const isNearBottom = (): boolean => {
  if (!messagesContainer.value) return true;

  const { scrollTop, scrollHeight, clientHeight } = messagesContainer.value;
  return scrollHeight - scrollTop - clientHeight < 100;
};

const scrollToBottom = async () => {
  await nextTick();

  if (messagesContainer.value) {
    messagesContainer.value.scrollTop = messagesContainer.value.scrollHeight;
  }
};

const handleScroll = () => {
  const nearBottom = isNearBottom();
  userIsScrolling.value = !nearBottom;

  if (scrollTimeout !== null) {
    clearTimeout(scrollTimeout);
  }

  if (nearBottom) {
    scrollTimeout = window.setTimeout(() => {
      userIsScrolling.value = false;
    }, 150);
  }
};

watch(
  () => props.messages.length,
  () => {
    if (!userIsScrolling.value) {
      scrollToBottom();
    }
  }
);

watch(
  () => {
    const lastMessage = props.messages[props.messages.length - 1];
    if (lastMessage && lastMessage.isStreaming && lastMessage.messageType === 'ai') {
      return lastMessage.content;
    }

    return null;
  },
  (newContent) => {
    if (newContent !== null && !userIsScrolling.value) {
      scrollToBottom();
    }
  }
);

onMounted(() => {
  messagesContainer.value?.addEventListener('scroll', handleScroll);
});

onUnmounted(() => {
  messagesContainer.value?.removeEventListener('scroll', handleScroll);
  if (scrollTimeout !== null) {
    clearTimeout(scrollTimeout);
  }
});

defineExpose({
  scrollToBottom,
});
</script>

<style scoped>
.chat-messages {
  flex: 1 1 0;
  min-height: 0;
  overflow-y: auto;
  overscroll-behavior: contain;
  padding: 24px;
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.empty-chat {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--theme-text-tertiary);
}

.empty-icon {
  width: 72px;
  height: 72px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
}

.empty-logo {
  width: 72px;
  height: 72px;
  object-fit: contain;
  filter: drop-shadow(0 12px 24px rgba(10, 132, 255, 0.16));
}
</style>
