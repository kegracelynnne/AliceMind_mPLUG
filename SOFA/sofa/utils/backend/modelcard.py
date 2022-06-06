# coding=utf-8
# Copyright 2018 The HuggingFace Inc. team.
# Copyright 2021-2022 The Alibaba DAMO NLP Team Authors.
# All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
""" Configuration base class and utilities."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from dataclasses import dataclass

from .auto.modeling_auto import (
    MODEL_FOR_AUDIO_CLASSIFICATION_MAPPING_NAMES,
    MODEL_FOR_CAUSAL_LM_MAPPING_NAMES,
    MODEL_FOR_IMAGE_CLASSIFICATION_MAPPING_NAMES,
    MODEL_FOR_IMAGE_SEGMENTATION_MAPPING_NAMES,
    MODEL_FOR_MASKED_LM_MAPPING_NAMES,
    MODEL_FOR_OBJECT_DETECTION_MAPPING_NAMES,
    MODEL_FOR_QUESTION_ANSWERING_MAPPING_NAMES,
    MODEL_FOR_SEQ_TO_SEQ_CAUSAL_LM_MAPPING_NAMES,
    MODEL_FOR_SEQUENCE_CLASSIFICATION_MAPPING_NAMES,
    MODEL_FOR_TABLE_QUESTION_ANSWERING_MAPPING_NAMES,
    MODEL_FOR_TOKEN_CLASSIFICATION_MAPPING_NAMES,
)
from .file_utils import (
    is_datasets_available,
    is_tf_available,
    is_tokenizers_available,
    is_torch_available,
)
from .training_args import ParallelMode
from .utils import logging

TASK_MAPPING = {
    "text-generation": MODEL_FOR_CAUSAL_LM_MAPPING_NAMES,
    "image-classification": MODEL_FOR_IMAGE_CLASSIFICATION_MAPPING_NAMES,
    "image-segmentation": MODEL_FOR_IMAGE_SEGMENTATION_MAPPING_NAMES,
    "fill-mask": MODEL_FOR_MASKED_LM_MAPPING_NAMES,
    "object-detection": MODEL_FOR_OBJECT_DETECTION_MAPPING_NAMES,
    "question-answering": MODEL_FOR_QUESTION_ANSWERING_MAPPING_NAMES,
    "text2text-generation": MODEL_FOR_SEQ_TO_SEQ_CAUSAL_LM_MAPPING_NAMES,
    "text-classification": MODEL_FOR_SEQUENCE_CLASSIFICATION_MAPPING_NAMES,
    "table-question-answering": MODEL_FOR_TABLE_QUESTION_ANSWERING_MAPPING_NAMES,
    "token-classification": MODEL_FOR_TOKEN_CLASSIFICATION_MAPPING_NAMES,
    "audio-classification": MODEL_FOR_AUDIO_CLASSIFICATION_MAPPING_NAMES,
}

logger = logging.get_logger(__name__)


AUTOGENERATED_TRAINER_COMMENT = """
<!-- This model card has been generated automatically according to the information the Trainer had access to. You
should probably proofread and complete it, then remove this comment. -->
"""

AUTOGENERATED_KERAS_COMMENT = """
<!-- This model card has been generated automatically according to the information Keras had access to. You should
probably proofread and complete it, then remove this comment. -->
"""


TASK_TAG_TO_NAME_MAPPING = {
    "fill-mask": "Masked Language Modeling",
    "image-classification": "Image Classification",
    "image-segmentation": "Image Segmentation",
    "multiple-choice": "Multiple Choice",
    "object-detection": "Object Detection",
    "question-answering": "Question Answering",
    "summarization": "Summarization",
    "table-question-answering": "Table Question Answering",
    "text-classification": "Text Classification",
    "text-generation": "Causal Language Modeling",
    "text2text-generation": "Sequence-to-sequence Language Modeling",
    "token-classification": "Token Classification",
    "translation": "Translation",
    "zero-shot-classification": "Zero Shot Classification",
}


METRIC_TAGS = [
    "accuracy",
    "bleu",
    "f1",
    "matthews_correlation",
    "pearsonr",
    "precision",
    "recall",
    "rouge",
    "sacrebleu",
    "spearmanr",
]


def _listify(obj):
    if obj is None:
        return []
    elif isinstance(obj, str):
        return [obj]
    else:
        return obj


def _insert_values_as_list(metadata, name, values):
    if values is None:
        return metadata
    if isinstance(values, str):
        values = [values]
    values = [v for v in values if v is not None]
    if len(values) == 0:
        return metadata
    metadata[name] = values
    return metadata


def infer_metric_tags_from_eval_results(eval_results):
    if eval_results is None:
        return {}
    result = {}
    for key in eval_results.keys():
        if key.lower().replace(" ", "_") in METRIC_TAGS:
            result[key.lower().replace(" ", "_")] = key
        elif key.lower() == "rouge1":
            result["rouge"] = key
    return result


def _insert_value(metadata, name, value):
    if value is None:
        return metadata
    metadata[name] = value
    return metadata


def is_hf_dataset(dataset):
    if not is_datasets_available():
        return False

    from datasets import Dataset

    return isinstance(dataset, Dataset)


def _get_mapping_values(mapping):
    result = []
    for v in mapping.values():
        if isinstance(v, (tuple, list)):
            result += list(v)
        else:
            result.append(v)
    return result


@dataclass
class TrainingSummary:
    model_name: str
    language: Optional[Union[str, List[str]]] = None
    license: Optional[str] = None
    tags: Optional[Union[str, List[str]]] = None
    finetuned_from: Optional[str] = None
    tasks: Optional[Union[str, List[str]]] = None
    dataset: Optional[Union[str, List[str]]] = None
    dataset_tags: Optional[Union[str, List[str]]] = None
    dataset_args: Optional[Union[str, List[str]]] = None
    eval_results: Optional[Dict[str, float]] = None
    eval_lines: Optional[List[str]] = None
    hyperparameters: Optional[Dict[str, Any]] = None
    source: Optional[str] = "trainer"

    def __post_init__(self):
        pass

    def create_model_index(self, metric_mapping):
        model_index = {"name": self.model_name}

        # Dataset mapping tag -> name
        dataset_names = _listify(self.dataset)
        dataset_tags = _listify(self.dataset_tags)
        dataset_args = _listify(self.dataset_args)
        if len(dataset_args) < len(dataset_tags):
            dataset_args = dataset_args + [None] * (len(dataset_tags) - len(dataset_args))
        dataset_mapping = {tag: name for tag, name in zip(dataset_tags, dataset_names)}
        dataset_arg_mapping = {tag: arg for tag, arg in zip(dataset_tags, dataset_args)}

        task_mapping = {
            task: TASK_TAG_TO_NAME_MAPPING[task] for task in _listify(self.tasks) if task in TASK_TAG_TO_NAME_MAPPING
        }

        model_index["results"] = []

        if len(task_mapping) == 0 and len(dataset_mapping) == 0:
            return [model_index]
        if len(task_mapping) == 0:
            task_mapping = {None: None}
        if len(dataset_mapping) == 0:
            dataset_mapping = {None: None}

        # One entry per dataset and per task
        all_possibilities = [(task_tag, ds_tag) for task_tag in task_mapping for ds_tag in dataset_mapping]
        for task_tag, ds_tag in all_possibilities:
            result = {}
            if task_tag is not None:
                result["task"] = {"name": task_mapping[task_tag], "type": task_tag}

            if ds_tag is not None:
                result["dataset"] = {"name": dataset_mapping[ds_tag], "type": ds_tag}
                if dataset_arg_mapping[ds_tag] is not None:
                    result["dataset"]["args"] = dataset_arg_mapping[ds_tag]

            if len(metric_mapping) > 0:
                result["metrics"] = []
                for metric_tag, metric_name in metric_mapping.items():
                    result["metrics"].append(
                        {
                            "name": metric_name,
                            "type": metric_tag,
                            "value": self.eval_results[metric_name],
                        }
                    )

            # Remove partial results to avoid the model card being rejected.
            if "task" in result and "dataset" in result and "metrics" in result:
                model_index["results"].append(result)
            else:
                logger.info(f"Dropping the following result as it does not have all the necessary fields:\n{result}")

        return [model_index]

    def create_metadata(self):
        metric_mapping = infer_metric_tags_from_eval_results(self.eval_results)

        metadata = {}
        metadata = _insert_values_as_list(metadata, "language", self.language)
        # metadata = _insert_value(metadata, "license", self.license)
        metadata = _insert_values_as_list(metadata, "tags", self.tags)
        metadata = _insert_values_as_list(metadata, "datasets", self.dataset_tags)
        metadata = _insert_values_as_list(metadata, "metrics", list(metric_mapping.keys()))
        metadata["model-index"] = self.create_model_index(metric_mapping)

        return metadata

    def to_model_card(self):
        import yaml
        model_card = ""

        metadata = yaml.dump(self.create_metadata(), sort_keys=False)
        if len(metadata) > 0:
            model_card = f"---\n{metadata}---\n"

        # Now the model card for realsies.
        if self.source == "trainer":
            model_card += AUTOGENERATED_TRAINER_COMMENT
        else:
            model_card += AUTOGENERATED_KERAS_COMMENT

        model_card += f"\n# {self.model_name}\n\n"

        if self.finetuned_from is None:
            model_card += "This model was trained from scratch on "
        else:
            model_card += f"This model is a fine-tuned version of [{self.finetuned_from}](https://huggingface.co/{self.finetuned_from}) on "

        if self.dataset is None:
            model_card += "an unknown dataset."
        else:
            if isinstance(self.dataset, str):
                model_card += f"the {self.dataset} dataset."
            elif isinstance(self.dataset, (tuple, list)) and len(self.dataset) == 1:
                model_card += f"the {self.dataset[0]} dataset."
            else:
                model_card += (
                    ", ".join([f"the {ds}" for ds in self.dataset[:-1]]) + f" and the {self.dataset[-1]} datasets."
                )

        if self.eval_results is not None:
            model_card += "\nIt achieves the following results on the evaluation set:\n"
            model_card += "\n".join([f"- {name}: {_maybe_round(value)}" for name, value in self.eval_results.items()])
        model_card += "\n"

        model_card += "\n## Model description\n\nMore information needed\n"
        model_card += "\n## Intended uses & limitations\n\nMore information needed\n"
        model_card += "\n## Training and evaluation data\n\nMore information needed\n"

        model_card += "\n## Training procedure\n"
        model_card += "\n### Training hyperparameters\n"
        if self.hyperparameters is not None:
            model_card += "\nThe following hyperparameters were used during training:\n"
            model_card += "\n".join([f"- {name}: {value}" for name, value in self.hyperparameters.items()])
            model_card += "\n"
        else:
            model_card += "\nMore information needed\n"

        if self.eval_lines is not None:
            model_card += "\n### Training results\n\n"
            model_card += make_markdown_table(self.eval_lines)
            model_card += "\n"

        model_card += "\n### Framework versions\n\n"
        # model_card += f"- Framework {__version__}\n"

        if self.source == "trainer" and is_torch_available():
            import torch

            model_card += f"- Pytorch {torch.__version__}\n"
        elif self.source == "keras" and is_tf_available():
            import tensorflow as tf

            model_card += f"- TensorFlow {tf.__version__}\n"
        if is_datasets_available():
            import datasets

            model_card += f"- Datasets {datasets.__version__}\n"
        if is_tokenizers_available():
            import tokenizers

            model_card += f"- Tokenizers {tokenizers.__version__}\n"

        return model_card

    @classmethod
    def from_trainer(
        cls,
        trainer,
        language=None,
        license=None,
        tags=None,
        model_name=None,
        finetuned_from=None,
        tasks=None,
        dataset_tags=None,
        dataset=None,
        dataset_args=None,
    ):
        # Infer default from dataset
        one_dataset = trainer.train_dataset if trainer.train_dataset is not None else trainer.eval_dataset
        if is_hf_dataset(one_dataset) and (dataset_tags is None or dataset_args is None):
            default_tag = one_dataset.builder_name
            # Those are not real datasets from the Hub so we exclude them.
            if default_tag not in ["csv", "json", "pandas", "parquet", "text"]:
                if dataset_tags is None:
                    dataset_tags = [default_tag]
                if dataset_args is None:
                    dataset_args = [one_dataset.config_name]

        if dataset is None and dataset_tags is not None:
            dataset = dataset_tags

        # Infer default finetuned_from
        if (
            finetuned_from is None
            and hasattr(trainer.model.config, "_name_or_path")
            and not os.path.isdir(trainer.model.config._name_or_path)
        ):
            finetuned_from = trainer.model.config._name_or_path

        # Infer default task tag:
        if tasks is None:
            model_class_name = trainer.model.__class__.__name__
            for task, mapping in TASK_MAPPING.items():
                if model_class_name in _get_mapping_values(mapping):
                    tasks = task

        if model_name is None:
            model_name = Path(trainer.args.output_dir).name

        # Add `generated_from_trainer` to the tags
        if tags is None:
            tags = ["generated_from_trainer"]
        elif isinstance(tags, str) and tags != "generated_from_trainer":
            tags = [tags, "generated_from_trainer"]
        elif "generated_from_trainer" not in tags:
            tags.append("generated_from_trainer")

        _, eval_lines, eval_results = parse_log_history(trainer.state.log_history)
        hyperparameters = extract_hyperparameters_from_trainer(trainer)

        return cls(
            language=language,
            license=license,
            tags=tags,
            model_name=model_name,
            finetuned_from=finetuned_from,
            tasks=tasks,
            dataset_tags=dataset_tags,
            dataset=dataset,
            dataset_args=dataset_args,
            eval_results=eval_results,
            eval_lines=eval_lines,
            hyperparameters=hyperparameters,
        )

    @classmethod
    def from_keras(
        cls,
        model,
        model_name,
        keras_history=None,
        language=None,
        license=None,
        tags=None,
        finetuned_from=None,
        tasks=None,
        dataset_tags=None,
        dataset=None,
        dataset_args=None,
    ):
        # Infer default from dataset
        if dataset is not None:
            if is_hf_dataset(dataset) and (dataset_tags is None or dataset_args is None):
                default_tag = dataset.builder_name
                # Those are not real datasets from the Hub so we exclude them.
                if default_tag not in ["csv", "json", "pandas", "parquet", "text"]:
                    if dataset_tags is None:
                        dataset_tags = [default_tag]
                    if dataset_args is None:
                        dataset_args = [dataset.config_name]

        if dataset is None and dataset_tags is not None:
            dataset = dataset_tags

        # Infer default finetuned_from
        if (
            finetuned_from is None
            and hasattr(model.config, "_name_or_path")
            and not os.path.isdir(model.config._name_or_path)
        ):
            finetuned_from = model.config._name_or_path

        # Infer default task tag:
        if tasks is None:
            model_class_name = model.__class__.__name__
            for task, mapping in TASK_MAPPING.items():
                if model_class_name in _get_mapping_values(mapping):
                    tasks = task

        # Add `generated_from_keras_callback` to the tags
        if tags is None:
            tags = ["generated_from_keras_callback"]
        elif isinstance(tags, str) and tags != "generated_from_keras_callback":
            tags = [tags, "generated_from_keras_callback"]
        elif "generated_from_trainer" not in tags:
            tags.append("generated_from_keras_callback")

        if keras_history is not None:
            _, eval_lines, eval_results = parse_keras_history(keras_history)
        else:
            eval_lines = []
            eval_results = dict()
        hyperparameters = extract_hyperparameters_from_keras(model)

        return cls(
            language=language,
            license=license,
            tags=tags,
            model_name=model_name,
            finetuned_from=finetuned_from,
            tasks=tasks,
            dataset_tags=dataset_tags,
            dataset=dataset,
            dataset_args=dataset_args,
            eval_results=eval_results,
            eval_lines=eval_lines,
            hyperparameters=hyperparameters,
            source="keras",
        )


def parse_keras_history(logs):
    """
    Parse the `logs` of either a `tf.keras.History` object returned by `model.fit()` or an accumulated logs `dict`
    passed to the `PushToHubCallback`. Returns lines and logs compatible with those returned by `parse_log_history`.
    """
    if hasattr(logs, "history"):
        # This looks like a `History` object
        logs.history["epoch"] = logs.epoch
        logs = logs.history
    else:
        # Training logs is a list of dicts, let's invert it to a dict of lists to match a History object
        logs = {log_key: [single_dict[log_key] for single_dict in logs] for log_key in logs[0]}

    lines = []
    for i in range(len(logs["epoch"])):
        epoch_dict = {log_key: log_value_list[i] for log_key, log_value_list in logs.items()}
        values = dict()
        for k, v in epoch_dict.items():
            if k.startswith("val_"):
                k = "validation_" + k[4:]
            elif k != "epoch":
                k = "train_" + k
            splits = k.split("_")
            name = " ".join([part.capitalize() for part in splits])
            values[name] = v
        lines.append(values)

    eval_results = lines[-1]

    return logs, lines, eval_results


def parse_log_history(log_history):
    """
    Parse the `log_history` of a Trainer to get the intermediate and final evaluation results.
    """
    idx = 0
    while idx < len(log_history) and "train_runtime" not in log_history[idx]:
        idx += 1

    # If there are no training logs
    if idx == len(log_history):
        idx -= 1
        while idx >= 0 and "eval_loss" not in log_history[idx]:
            idx -= 1

        if idx > 0:
            return None, None, log_history[idx]
        else:
            return None, None, None

    # From now one we can assume we have training logs:
    train_log = log_history[idx]
    lines = []
    training_loss = "No log"
    for i in range(idx):
        if "loss" in log_history[i]:
            training_loss = log_history[i]["loss"]
        if "eval_loss" in log_history[i]:
            metrics = log_history[i].copy()
            _ = metrics.pop("total_flos", None)
            epoch = metrics.pop("epoch", None)
            step = metrics.pop("step", None)
            _ = metrics.pop("eval_runtime", None)
            _ = metrics.pop("eval_samples_per_second", None)
            _ = metrics.pop("eval_steps_per_second", None)
            values = {"Training Loss": training_loss, "Epoch": epoch, "Step": step}
            for k, v in metrics.items():
                if k == "eval_loss":
                    values["Validation Loss"] = v
                else:
                    splits = k.split("_")
                    name = " ".join([part.capitalize() for part in splits[1:]])
                    values[name] = v
            lines.append(values)

    idx = len(log_history) - 1
    while idx >= 0 and "eval_loss" not in log_history[idx]:
        idx -= 1

    if idx > 0:
        eval_results = {}
        for key, value in log_history[idx].items():
            if key.startswith("eval_"):
                key = key[5:]
            if key not in ["runtime", "samples_per_second", "steps_per_second", "epoch", "step"]:
                camel_cased_key = " ".join([part.capitalize() for part in key.split("_")])
                eval_results[camel_cased_key] = value
        return train_log, lines, eval_results
    else:
        return train_log, lines, None


def extract_hyperparameters_from_keras(model):
    import tensorflow as tf

    hyperparameters = dict()
    if hasattr(model, "optimizer") and model.optimizer is not None:
        hyperparameters["optimizer"] = model.optimizer.get_config()
    else:
        hyperparameters["optimizer"] = None
    hyperparameters["training_precision"] = tf.keras.mixed_precision.global_policy().name

    return hyperparameters


def _maybe_round(v, decimals=4):
    if isinstance(v, float) and len(str(v).split(".")) > 1 and len(str(v).split(".")[1]) > decimals:
        return f"{v:.{decimals}f}"
    return str(v)


def _regular_table_line(values, col_widths):
    values_with_space = [f"| {v}" + " " * (w - len(v) + 1) for v, w in zip(values, col_widths)]
    return "".join(values_with_space) + "|\n"


def _second_table_line(col_widths):
    values = ["|:" + "-" * w + ":" for w in col_widths]
    return "".join(values) + "|\n"


def make_markdown_table(lines):
    """
    Create a nice Markdown table from the results in `lines`.
    """
    if lines is None or len(lines) == 0:
        return ""
    col_widths = {key: len(str(key)) for key in lines[0].keys()}
    for line in lines:
        for key, value in line.items():
            if col_widths[key] < len(_maybe_round(value)):
                col_widths[key] = len(_maybe_round(value))

    table = _regular_table_line(list(lines[0].keys()), list(col_widths.values()))
    table += _second_table_line(list(col_widths.values()))
    for line in lines:
        table += _regular_table_line([_maybe_round(v) for v in line.values()], list(col_widths.values()))
    return table


_TRAINING_ARGS_KEYS = [
    "learning_rate",
    "train_batch_size",
    "eval_batch_size",
    "seed",
]


def extract_hyperparameters_from_trainer(trainer):
    hyperparameters = {k: getattr(trainer.args, k) for k in _TRAINING_ARGS_KEYS}

    if trainer.args.parallel_mode not in [ParallelMode.NOT_PARALLEL, ParallelMode.NOT_DISTRIBUTED]:
        hyperparameters["distributed_type"] = (
            "multi-GPU" if trainer.args.parallel_mode == ParallelMode.DISTRIBUTED else trainer.args.parallel_mode.value
        )
    if trainer.args.world_size > 1:
        hyperparameters["num_devices"] = trainer.args.world_size
    if trainer.args.gradient_accumulation_steps > 1:
        hyperparameters["gradient_accumulation_steps"] = trainer.args.gradient_accumulation_steps

    total_train_batch_size = (
        trainer.args.train_batch_size * trainer.args.world_size * trainer.args.gradient_accumulation_steps
    )
    if total_train_batch_size != hyperparameters["train_batch_size"]:
        hyperparameters["total_train_batch_size"] = total_train_batch_size
    total_eval_batch_size = trainer.args.eval_batch_size * trainer.args.world_size
    if total_eval_batch_size != hyperparameters["eval_batch_size"]:
        hyperparameters["total_eval_batch_size"] = total_eval_batch_size

    if trainer.args.adafactor:
        hyperparameters["optimizer"] = "Adafactor"
    else:
        hyperparameters[
            "optimizer"
        ] = f"Adam with betas=({trainer.args.adam_beta1},{trainer.args.adam_beta2}) and epsilon={trainer.args.adam_epsilon}"

    hyperparameters["lr_scheduler_type"] = trainer.args.lr_scheduler_type.value
    if trainer.args.warmup_ratio != 0.0:
        hyperparameters["lr_scheduler_warmup_ratio"] = trainer.args.warmup_ratio
    if trainer.args.warmup_steps != 0.0:
        hyperparameters["lr_scheduler_warmup_steps"] = trainer.args.warmup_steps
    if trainer.args.max_steps != -1:
        hyperparameters["training_steps"] = trainer.args.max_steps
    else:
        hyperparameters["num_epochs"] = trainer.args.num_train_epochs

    if trainer.args.fp16:
        if trainer.use_amp:
            hyperparameters["mixed_precision_training"] = "Native AMP"
        elif trainer.use_apex:
            hyperparameters["mixed_precision_training"] = f"Apex, opt level {trainer.args.fp16_opt_level}"

    if trainer.args.label_smoothing_factor != 0.0:
        hyperparameters["label_smoothing_factor"] = trainer.args.label_smoothing_factor

    return hyperparameters