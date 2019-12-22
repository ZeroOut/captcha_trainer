import os
import re
import math
import sys
import shutil
import json
import traceback
import PIL.Image as PilImage
import threading
import tkinter as tk
from tkinter import messagebox
from tkinter import ttk
from tkinter import filedialog
from constants import *
from config import ModelConfig, OUTPUT_SHAPE1_MAP, NETWORK_MAP, DataAugmentationEntity, PretreatmentEntity
from make_dataset import DataSets
from trains import Trains
from category import category_extract, SIMPLE_CATEGORY_MODEL
from gui.utils import LayoutGUI
from gui.data_augmentation import DataAugmentationDialog
from gui.pretreatment import PretreatmentDialog


class Wizard:

    job: threading.Thread
    current_task: Trains
    is_task_running: bool = False
    data_augmentation_entity = DataAugmentationEntity()
    pretreatment_entity = PretreatmentEntity()

    def __init__(self, parent: tk.Tk):
        self.layout = {
            'global': {
                'start': {'x': 15, 'y': 20},
                'space': {'x': 15, 'y': 25},
                'tiny_space': {'x': 5, 'y': 10}
            }
        }
        self.parent = parent
        self.parent.iconbitmap(Wizard.resource_path("resource/icon.ico"))
        self.current_project: str = ""
        self.project_root_path = "./projects"
        if not os.path.exists(self.project_root_path):
            os.makedirs(self.project_root_path)
        self.parent.title('Image Classification Wizard Tool based on Deep Learning')
        self.parent.resizable(width=False, height=False)
        self.window_width = 815
        self.window_height = 700
        self.layout_utils = LayoutGUI(self.layout, self.window_width)
        screenwidth = self.parent.winfo_screenwidth()
        screenheight = self.parent.winfo_screenheight()
        size = '%dx%d+%d+%d' % (
            self.window_width,
            self.window_height,
            (screenwidth - self.window_width) / 2,
            (screenheight - self.window_height) / 2
        )

        self.parent.bind('<Button-1>', lambda x: self.blank_click(x))

        # ============================= Menu 1 =====================================
        self.menubar = tk.Menu(self.parent)
        self.data_menu = tk.Menu(self.menubar, tearoff=False)
        self.help_menu = tk.Menu(self.menubar, tearoff=False)
        self.system_menu = tk.Menu(self.menubar, tearoff=False)
        self.edit_var = tk.DoubleVar()
        self.memory_usage_menu = tk.Menu(self.menubar, tearoff=False)
        self.memory_usage_menu.add_radiobutton(label="50%", variable=self.edit_var, value=0.5)
        self.memory_usage_menu.add_radiobutton(label="60%", variable=self.edit_var, value=0.6)
        self.memory_usage_menu.add_radiobutton(label="70%", variable=self.edit_var, value=0.7)
        self.memory_usage_menu.add_radiobutton(label="80%", variable=self.edit_var, value=0.8)

        self.menubar.add_cascade(label="System", menu=self.system_menu)
        self.system_menu.add_cascade(label="Memory Usage", menu=self.memory_usage_menu)

        self.data_menu.add_command(label="Data Augmentation", command=lambda: self.popup_data_augmentation())
        self.data_menu.add_command(label="Pretreatment", command=lambda: self.popup_pretreatment())
        self.data_menu.add_separator()
        self.data_menu.add_command(label="Clear Dataset", command=lambda: self.clear_dataset())
        self.menubar.add_cascade(label="Data", menu=self.data_menu)

        self.help_menu.add_command(label="About", command=lambda: self.popup_about())
        self.menubar.add_cascade(label="Help", menu=self.help_menu)

        self.parent.config(menu=self.menubar)

        # ============================= Group 1 =====================================
        self.label_frame_source = ttk.Labelframe(self.parent, text='Sample Source')
        self.label_frame_source.place(
            x=self.layout['global']['start']['x'],
            y=self.layout['global']['start']['y'],
            width=790,
            height=150
        )

        # 训练集源路径 - 标签
        self.dataset_train_path_text = ttk.Label(self.parent, text='Training Path', anchor=tk.W)
        self.layout_utils.inside_widget(
            src=self.dataset_train_path_text,
            target=self.label_frame_source,
            width=90,
            height=20
        )

        # 训练集源路径 - 输入控件
        self.source_train_path_listbox = tk.Listbox(self.parent, font=('微软雅黑', 9))
        self.layout_utils.next_to_widget(
            src=self.source_train_path_listbox,
            target=self.dataset_train_path_text,
            width=600,
            height=50,
            tiny_space=True
        )
        self.source_train_path_listbox.bind(
            sequence="<Delete>",
            func=lambda x: self.listbox_delete_item_callback(x, self.source_train_path_listbox)
        )
        self.listbox_scrollbar(self.source_train_path_listbox)

        # 训练集源路径 - 按钮
        self.btn_browse_train = ttk.Button(
            self.parent, text='Browse', command=lambda: self.browse_dataset(DatasetType.Directory, RunMode.Trains)
        )
        self.layout_utils.next_to_widget(
            src=self.btn_browse_train,
            target=self.source_train_path_listbox,
            width=60,
            height=24,
            tiny_space=True
        )

        # 验证集源路径 - 标签
        label_edge = self.layout_utils.object_edge_info(self.dataset_train_path_text)
        widget_edge = self.layout_utils.object_edge_info(self.source_train_path_listbox)
        self.dataset_validation_path_text = ttk.Label(self.parent, text='Validation Path', anchor=tk.W)
        self.dataset_validation_path_text.place(
            x=label_edge['x'],
            y=widget_edge['edge_y'] + self.layout['global']['space']['y'] / 2,
            width=90,
            height=20
        )

        # 验证集源路径 - 输入控件
        self.source_validation_path_listbox = tk.Listbox(self.parent, font=('微软雅黑', 9))
        self.layout_utils.next_to_widget(
            src=self.source_validation_path_listbox,
            target=self.dataset_validation_path_text,
            width=600,
            height=50,
            tiny_space=True
        )
        self.source_validation_path_listbox.bind(
            sequence="<Delete>",
            func=lambda x: self.listbox_delete_item_callback(x, self.source_validation_path_listbox)
        )
        self.listbox_scrollbar(self.source_validation_path_listbox)

        # 训练集源路径 - 按钮
        self.btn_browse_validation = ttk.Button(
            self.parent, text='Browse', command=lambda: self.browse_dataset(DatasetType.Directory, RunMode.Validation)
        )
        self.layout_utils.next_to_widget(
            src=self.btn_browse_validation,
            target=self.source_validation_path_listbox,
            width=60,
            height=24,
            tiny_space=True
        )

        # ============================= Group 2 =====================================
        self.label_frame_neu = ttk.Labelframe(self.parent, text='Neural network')
        self.layout_utils.below_widget(
            src=self.label_frame_neu,
            target=self.label_frame_source,
            width=790,
            height=120,
            tiny_space=False
        )

        # 最大标签数目 - 标签
        self.label_num_text = ttk.Label(self.parent, text='Label Num', anchor=tk.W)
        self.layout_utils.inside_widget(
            src=self.label_num_text,
            target=self.label_frame_neu,
            width=65,
            height=20,
        )

        # 最大标签数目 - 滚动框
        self.label_num_spin = ttk.Spinbox(self.parent, from_=1, to=12)
        self.label_num_spin.set(1)
        self.layout_utils.next_to_widget(
            src=self.label_num_spin,
            target=self.label_num_text,
            width=50,
            height=20,
            tiny_space=True
        )

        # 图像通道 - 标签
        self.channel_text = ttk.Label(self.parent, text='Channel', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.channel_text,
            target=self.label_num_spin,
            width=50,
            height=20,
            tiny_space=False
        )

        # 图像通道 - 下拉框
        self.comb_channel = ttk.Combobox(self.parent, values=(3, 1), state='readonly')
        self.comb_channel.current(0)
        self.layout_utils.next_to_widget(
            src=self.comb_channel,
            target=self.channel_text,
            width=38,
            height=20,
            tiny_space=True
        )

        # 卷积层 - 标签
        self.neu_cnn_text = ttk.Label(self.parent, text='CNN Layer', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.neu_cnn_text,
            target=self.comb_channel,
            width=65,
            height=20,
            tiny_space=False
        )

        # 卷积层 - 下拉框
        self.comb_neu_cnn = ttk.Combobox(self.parent, values=[_.name for _ in CNNNetwork], state='readonly')
        self.comb_neu_cnn.current(0)
        self.layout_utils.next_to_widget(
            src=self.comb_neu_cnn,
            target=self.neu_cnn_text,
            width=80,
            height=20,
            tiny_space=True
        )

        # 循环层 - 标签
        self.neu_recurrent_text = ttk.Label(self.parent, text='Recurrent Layer', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.neu_recurrent_text,
            target=self.comb_neu_cnn,
            width=95,
            height=20,
            tiny_space=False
        )

        # 循环层 - 下拉框
        self.comb_recurrent = ttk.Combobox(self.parent, values=[_.name for _ in RecurrentNetwork], state='readonly')
        self.comb_recurrent.current(0)
        self.layout_utils.next_to_widget(
            src=self.comb_recurrent,
            target=self.neu_recurrent_text,
            width=112,
            height=20,
            tiny_space=True
        )
        self.comb_recurrent.bind("<<ComboboxSelected>>", lambda x: self.auto_loss(x))

        # 循环层单元数 - 标签
        self.units_num_text = ttk.Label(self.parent, text='UnitsNum', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.units_num_text,
            target=self.comb_recurrent,
            width=60,
            height=20,
            tiny_space=False
        )

        # 循环层单元数 - 下拉框
        self.units_num_spin = ttk.Spinbox(self.parent, from_=16, to=512, increment=16, wrap=True)
        self.units_num_spin.set(64)
        self.layout_utils.next_to_widget(
            src=self.units_num_spin,
            target=self.units_num_text,
            width=55,
            height=20,
            tiny_space=True
        )

        # 损失函数 - 标签
        self.loss_func_text = ttk.Label(self.parent, text='Loss Function', anchor=tk.W)
        self.layout_utils.below_widget(
            src=self.loss_func_text,
            target=self.label_num_text,
            width=85,
            height=20,
            tiny_space=True
        )

        # 损失函数 - 下拉框
        self.comb_loss = ttk.Combobox(self.parent, values=[_.name for _ in LossFunction], state='readonly')
        self.comb_loss.current(0)
        self.layout_utils.next_to_widget(
            src=self.comb_loss,
            target=self.loss_func_text,
            width=101,
            height=20,
            tiny_space=True
        )

        # 优化器 - 标签
        self.optimizer_text = ttk.Label(self.parent, text='Optimizer', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.optimizer_text,
            target=self.comb_loss,
            width=60,
            height=20,
            tiny_space=False
        )

        # 优化器 - 下拉框
        self.comb_optimizer = ttk.Combobox(self.parent, values=[_.name for _ in Optimizer], state='readonly')
        self.comb_optimizer.current(0)
        self.layout_utils.next_to_widget(
            src=self.comb_optimizer,
            target=self.optimizer_text,
            width=88,
            height=20,
            tiny_space=True
        )

        # 学习率 - 标签
        self.learning_rate_text = ttk.Label(self.parent, text='Learning Rate', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.learning_rate_text,
            target=self.comb_optimizer,
            width=85,
            height=20,
            tiny_space=False
        )

        # 学习率 - 滚动框
        self.learning_rate_spin = ttk.Spinbox(self.parent, from_=0.00001, to=0.1, increment='0.0001')
        self.learning_rate_spin.set(0.001)
        self.layout_utils.next_to_widget(
            src=self.learning_rate_spin,
            target=self.learning_rate_text,
            width=67,
            height=20,
            tiny_space=True
        )

        # Resize - 标签
        self.resize_text = ttk.Label(self.parent, text='Resize', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.resize_text,
            target=self.learning_rate_spin,
            width=36,
            height=20,
            tiny_space=False
        )

        # Resize - 输入框
        self.resize_val = tk.StringVar()
        self.resize_val.set('[150, 50]')
        self.resize_entry = ttk.Entry(self.parent, textvariable=self.resize_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.resize_entry,
            target=self.resize_text,
            width=60,
            height=20,
            tiny_space=True
        )

        # Size - 标签
        self.size_text = ttk.Label(self.parent, text='Size', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.size_text,
            target=self.resize_entry,
            width=30,
            height=20,
            tiny_space=False
        )

        # Size - 输入框
        self.size_val = tk.StringVar()
        self.size_val.set('[-1, -1]')
        self.size_entry = ttk.Entry(self.parent, textvariable=self.size_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.size_entry,
            target=self.size_text,
            width=60,
            height=20,
            tiny_space=True
        )

        # 类别 - 标签
        self.category_text = ttk.Label(self.parent, text='Category', anchor=tk.W)
        self.layout_utils.below_widget(
            src=self.category_text,
            target=self.loss_func_text,
            width=72,
            height=20,
            tiny_space=True
        )

        # 类别 - 下拉框
        self.comb_category = ttk.Combobox(self.parent, values=(
            'CUSTOMIZED',
            'NUMERIC',
            'ALPHANUMERIC',
            'ALPHANUMERIC_LOWER',
            'ALPHANUMERIC_UPPER',
            'ALPHABET_LOWER',
            'ALPHABET_UPPER',
            'ALPHABET',
            'ARITHMETIC',
            'FLOAT',
            'CHS_3500',
            'ALPHANUMERIC_CHS_3500_LOWER'
        ), state='readonly')
        self.comb_category.current(1)
        self.comb_category.bind("<<ComboboxSelected>>", lambda x: self.comb_category_callback(x))
        self.layout_utils.next_to_widget(
            src=self.comb_category,
            target=self.category_text,
            width=225,
            height=20,
            tiny_space=True
        )

        # 类别 - 自定义输入框
        self.category_val = tk.StringVar()
        self.category_val.set('')
        self.category_entry = ttk.Entry(self.parent, textvariable=self.category_val, justify=tk.LEFT, state=tk.DISABLED)
        self.layout_utils.next_to_widget(
            src=self.category_entry,
            target=self.comb_category,
            width=440,
            height=20,
            tiny_space=False
        )

        # ============================= Group 3 =====================================
        self.label_frame_train = ttk.Labelframe(self.parent, text='Training Configuration')
        self.layout_utils.below_widget(
            src=self.label_frame_train,
            target=self.label_frame_neu,
            width=790,
            height=60,
            tiny_space=True
        )

        # 任务完成标准 - 准确率 - 标签
        self.end_acc_text = ttk.Label(self.parent, text='End Accuracy', anchor=tk.W)
        self.layout_utils.inside_widget(
            src=self.end_acc_text,
            target=self.label_frame_train,
            width=85,
            height=20,
        )

        # 任务完成标准 - 准确率 - 输入框
        self.end_acc_val = tk.DoubleVar()
        self.end_acc_val.set(0.95)
        self.end_acc_entry = ttk.Entry(self.parent, textvariable=self.end_acc_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.end_acc_entry,
            target=self.end_acc_text,
            width=56,
            height=20,
            tiny_space=True
        )

        # 任务完成标准 - 平均损失 - 标签
        self.end_cost_text = ttk.Label(self.parent, text='End Cost', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.end_cost_text,
            target=self.end_acc_entry,
            width=60,
            height=20,
            tiny_space=False
        )

        # 任务完成标准 - 平均损失 - 输入框
        self.end_cost_val = tk.DoubleVar()
        self.end_cost_val.set(0.5)
        self.end_cost_entry = ttk.Entry(self.parent, textvariable=self.end_cost_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.end_cost_entry,
            target=self.end_cost_text,
            width=58,
            height=20,
            tiny_space=True
        )

        # 任务完成标准 - 循环轮次 - 标签
        self.end_epochs_text = ttk.Label(self.parent, text='End Epochs', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.end_epochs_text,
            target=self.end_cost_entry,
            width=72,
            height=20,
            tiny_space=False
        )

        # 任务完成标准 - 循环轮次 - 输入框
        self.end_epochs_spin = ttk.Spinbox(self.parent, from_=0, to=10000)
        self.end_epochs_spin.set(2)
        self.layout_utils.next_to_widget(
            src=self.end_epochs_spin,
            target=self.end_epochs_text,
            width=50,
            height=20,
            tiny_space=True
        )

        # 训练批次大小 - 标签
        self.batch_size_text = ttk.Label(self.parent, text='Train BatchSize', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.batch_size_text,
            target=self.end_epochs_spin,
            width=90,
            height=20,
            tiny_space=False
        )

        # 训练批次大小 - 输入框
        self.batch_size_val = tk.IntVar()
        self.batch_size_val.set(64)
        self.batch_size_entry = ttk.Entry(self.parent, textvariable=self.batch_size_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.batch_size_entry,
            target=self.batch_size_text,
            width=40,
            height=20,
            tiny_space=True
        )

        # 验证批次大小 - 标签
        self.validation_batch_size_text = ttk.Label(self.parent, text='Validation BatchSize', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.validation_batch_size_text,
            target=self.batch_size_entry,
            width=120,
            height=20,
            tiny_space=False
        )

        # 验证批次大小 - 输入框
        self.validation_batch_size_val = tk.IntVar()
        self.validation_batch_size_val.set(300)
        self.validation_batch_size_entry = ttk.Entry(self.parent, textvariable=self.validation_batch_size_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.validation_batch_size_entry,
            target=self.validation_batch_size_text,
            width=40,
            height=20,
            tiny_space=True
        )



        # ============================= Group 5 =====================================
        self.label_frame_project = ttk.Labelframe(self.parent, text='Project Configuration')
        self.layout_utils.below_widget(
            src=self.label_frame_project,
            target=self.label_frame_train,
            width=790,
            height=60,
            tiny_space=True
        )

        # 项目名 - 标签
        self.project_name_text = ttk.Label(self.parent, text='Project Name', anchor=tk.W)
        self.layout_utils.inside_widget(
            src=self.project_name_text,
            target=self.label_frame_project,
            width=90,
            height=20
        )

        # 项目名 - 下拉输入框
        self.comb_project_name = ttk.Combobox(self.parent)
        self.layout_utils.next_to_widget(
            src=self.comb_project_name,
            target=self.project_name_text,
            width=430,
            height=20,
            tiny_space=True
        )
        self.comb_project_name.bind(
            sequence="<Return>",
            func=lambda x: self.project_name_fill_callback(x)
        )
        self.comb_project_name.bind(
            sequence="<Button-1>",
            func=lambda x: self.fetch_projects()
        )
        self.comb_project_name.bind("<<ComboboxSelected>>", lambda x: self.read_conf(x))

        # 保存配置 - 按钮
        self.btn_save_conf = ttk.Button(
            self.parent, text='Save Configuration', command=lambda: self.save_conf()
        )
        self.layout_utils.next_to_widget(
            src=self.btn_save_conf,
            target=self.comb_project_name,
            width=130,
            height=24,
            tiny_space=False,
            offset_y=-2
        )

        # 删除项目 - 按钮
        self.btn_delete = ttk.Button(
            self.parent, text='Delete', command=lambda: self.delete_project()
        )
        self.layout_utils.next_to_widget(
            src=self.btn_delete,
            target=self.btn_save_conf,
            width=80,
            height=24,
            tiny_space=False,
        )

        # ============================= Group 6 =====================================
        self.label_frame_dataset = ttk.Labelframe(
            self.parent, text='Sample Dataset'
        )
        self.layout_utils.below_widget(
            src=self.label_frame_dataset,
            target=self.label_frame_project,
            width=790,
            height=170,
            tiny_space=True
        )

        # 附加训练集 - 按钮
        self.btn_attach_dataset = ttk.Button(
            self.parent,
            text='Attach Dataset',
            command=lambda: self.attach_dataset()
        )
        self.layout_utils.inside_widget(
            src=self.btn_attach_dataset,
            target=self.label_frame_dataset,
            width=120,
            height=24,
        )

        # 附加训练集 - 显示框
        self.attach_dataset_val = tk.StringVar()
        self.attach_dataset_val.set('')
        self.attach_dataset_entry = ttk.Entry(
            self.parent, textvariable=self.attach_dataset_val, justify=tk.LEFT, state=tk.DISABLED
        )
        self.layout_utils.next_to_widget(
            src=self.attach_dataset_entry,
            target=self.btn_attach_dataset,
            width=420,
            height=24,
            tiny_space=True
        )

        # 验证集数目 - 标签
        self.validation_num_text = ttk.Label(self.parent, text='Validation Set Num', anchor=tk.W)
        self.layout_utils.next_to_widget(
            src=self.validation_num_text,
            target=self.attach_dataset_entry,
            width=120,
            height=20,
            tiny_space=False,
            offset_y=2
        )

        # 验证集数目 - 输入框
        self.validation_num_val = tk.IntVar()
        self.validation_num_val.set(300)
        self.validation_num_entry = ttk.Entry(self.parent, textvariable=self.validation_num_val, justify=tk.LEFT)
        self.layout_utils.next_to_widget(
            src=self.validation_num_entry,
            target=self.validation_num_text,
            width=71,
            height=20,
            tiny_space=True
        )

        # 训练集路径 - 标签
        self.dataset_train_path_text = ttk.Label(self.parent, text='Training Dataset', anchor=tk.W)
        self.layout_utils.below_widget(
            src=self.dataset_train_path_text,
            target=self.btn_attach_dataset,
            width=100,
            height=20,
            tiny_space=False
        )

        # 训练集路径 - 列表框
        self.dataset_train_listbox = tk.Listbox(self.parent, font=('微软雅黑', 9))
        self.layout_utils.next_to_widget(
            src=self.dataset_train_listbox,
            target=self.dataset_train_path_text,
            width=640,
            height=36,
            tiny_space=False
        )
        self.dataset_train_listbox.bind(
            sequence="<Delete>",
            func=lambda x: self.listbox_delete_item_callback(x, self.dataset_train_listbox)
        )
        self.listbox_scrollbar(self.dataset_train_listbox)

        # 验证集路径 - 标签
        label_edge = self.layout_utils.object_edge_info(self.dataset_train_path_text)
        widget_edge = self.layout_utils.object_edge_info(self.dataset_train_listbox)
        self.dataset_validation_path_text = ttk.Label(self.parent, text='Validation Dataset', anchor=tk.W)
        self.dataset_validation_path_text.place(
            x=label_edge['x'],
            y=widget_edge['edge_y'] + self.layout['global']['space']['y'] / 2,
            width=100,
            height=20
        )

        # 验证集路径 - 下拉输入框
        self.dataset_validation_listbox = tk.Listbox(self.parent, font=('微软雅黑', 9))
        self.layout_utils.next_to_widget(
            src=self.dataset_validation_listbox,
            target=self.dataset_validation_path_text,
            width=640,
            height=36,
            tiny_space=False
        )
        self.dataset_validation_listbox.bind(
            sequence="<Delete>",
            func=lambda x: self.listbox_delete_item_callback(x, self.dataset_validation_listbox)
        )
        self.listbox_scrollbar(self.dataset_validation_listbox)

        self.sample_map = {
            DatasetType.Directory: {
                RunMode.Trains: self.source_train_path_listbox,
                RunMode.Validation: self.source_validation_path_listbox
            },
            DatasetType.TFRecords: {
                RunMode.Trains: self.dataset_train_listbox,
                RunMode.Validation: self.dataset_validation_listbox
            }
        }

        # 开始训练 - 按钮
        self.btn_training = ttk.Button(self.parent, text='Start Training', command=lambda: self.start_training())
        self.layout_utils.widget_from_right(
            src=self.btn_training,
            target=self.label_frame_dataset,
            width=120,
            height=24,
            tiny_space=True
        )

        # 终止训练 - 按钮
        self.btn_stop = ttk.Button(self.parent, text='Stop', command=lambda: self.stop_training())
        self.button_state(self.btn_stop, tk.DISABLED)
        self.layout_utils.before_widget(
            src=self.btn_stop,
            target=self.btn_training,
            width=60,
            height=24,
            tiny_space=True
        )

        # 编译模型 - 按钮
        self.btn_compile = ttk.Button(self.parent, text='Compile', command=lambda: self.compile())
        self.layout_utils.before_widget(
            src=self.btn_compile,
            target=self.btn_stop,
            width=80,
            height=24,
            tiny_space=True
        )

        # 打包训练集 - 按钮
        self.btn_make_dataset = ttk.Button(self.parent, text='Make Dataset', command=lambda: self.make_dataset())
        self.layout_utils.before_widget(
            src=self.btn_make_dataset,
            target=self.btn_compile,
            width=120,
            height=24,
            tiny_space=True
        )

        # 打包训练集 - 按钮
        self.btn_reset_history = ttk.Button(
            self.parent, text='Reset History', command=lambda: self.reset_history()
        )
        self.layout_utils.before_widget(
            src=self.btn_reset_history,
            target=self.btn_make_dataset,
            width=120,
            height=24,
            tiny_space=True
        )

        self.parent.geometry(size)

    @staticmethod
    def threading_exec(func, *args) -> threading.Thread:
        th = threading.Thread(target=func, args=args)
        th.setDaemon(True)
        th.start()
        return th

    def popup_data_augmentation(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        data_augmentation = DataAugmentationDialog()
        data_augmentation.read_conf(self.data_augmentation_entity)

    def popup_pretreatment(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        pretreatment = PretreatmentDialog()
        pretreatment.read_conf(self.pretreatment_entity)

    @staticmethod
    def listbox_scrollbar(listbox: tk.Listbox):
        y_scrollbar = tk.Scrollbar(
            listbox, command=listbox.yview
        )
        y_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        listbox.config(yscrollcommand=y_scrollbar.set)

    def blank_click(self, event):
        if self.current_project != self.comb_project_name.get():
            self.project_name_fill_callback(event)

    def project_name_fill_callback(self, event):
        suffix = '-{}-{}-H{}-{}-C{}'.format(
            self.comb_neu_cnn.get(),
            self.comb_recurrent.get(),
            self.units_num_spin.get(),
            self.comb_loss.get(),
            self.comb_channel.get(),
        )
        current_project_name = self.comb_project_name.get()
        if len(current_project_name) > 0 and current_project_name not in self.project_names:
            self.sample_map[DatasetType.Directory][RunMode.Trains].delete(0, tk.END)
            self.sample_map[DatasetType.Directory][RunMode.Validation].delete(0, tk.END)
            if not current_project_name.endswith(suffix):
                self.comb_project_name.insert(tk.END, suffix)
            self.current_project = self.comb_project_name.get()
            self.update_dataset_files_path(mode=RunMode.Trains)
            self.update_dataset_files_path(mode=RunMode.Validation)

    @property
    def project_path(self):
        if not self.current_project:
            return None
        project_path = "{}/{}".format(self.project_root_path, self.current_project)
        if not os.path.exists(project_path):
            os.makedirs(project_path)
        return project_path

    def update_dataset_files_path(self, mode: RunMode):
        dataset_name = "dataset/{}.0.tfrecords".format(mode.value)
        dataset_path = os.path.join(self.project_path, dataset_name)
        dataset_path = dataset_path.replace("\\", '/')
        self.sample_map[DatasetType.TFRecords][mode].delete(0, tk.END)
        self.sample_map[DatasetType.TFRecords][mode].insert(tk.END, dataset_path)
        self.save_conf()

    def attach_dataset(self):
        if self.is_task_running:
            messagebox.showerror(
                "Error!", "Please terminate the current training first or wait for the training to end."
            )
            return
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        filename = filedialog.askdirectory()
        if not filename:
            return
        model_conf = ModelConfig(self.current_project)

        if not self.check_dataset(model_conf):
            return

        self.attach_dataset_val.set(filename)
        self.button_state(self.btn_attach_dataset, tk.DISABLED)

        for mode in [RunMode.Trains, RunMode.Validation]:
            attached_dataset_name = model_conf.dataset_increasing_name(mode)
            attached_dataset_name = "dataset/{}".format(attached_dataset_name)
            attached_dataset_path = os.path.join(self.project_path, attached_dataset_name)
            attached_dataset_path = attached_dataset_path.replace("\\", '/')
            if mode == RunMode.Validation and self.validation_num_val.get() == 0:
                continue
            self.sample_map[DatasetType.TFRecords][mode].insert(tk.END, attached_dataset_path)
        self.save_conf()
        model_conf = ModelConfig(self.current_project)
        self.threading_exec(
            lambda: DataSets(model_conf).make_dataset(
                trains_path=filename,
                is_add=True,
                callback=lambda: self.button_state(self.btn_attach_dataset, tk.NORMAL),
                msg=lambda x: tk.messagebox.showinfo('Attach Dataset Status', x)
            )
        )
        pass

    @staticmethod
    def button_state(btn: ttk.Button, state: str):
        btn['state'] = state

    def delete_project(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please select a project to delete."
            )
            return
        if self.is_task_running:
            messagebox.showerror(
                "Error!", "Please terminate the current training first or wait for the training to end."
            )
            return
        project_path = "./projects/{}".format(self.current_project)
        try:
            shutil.rmtree(project_path)
        except Exception as e:
            messagebox.showerror(
                "Error!", json.dumps(e.args)
            )
        messagebox.showinfo(
            "Error!", "Delete successful!"
        )
        self.comb_project_name.delete(0, tk.END)

    def reset_history(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please select a project first."
            )
            return
        if self.is_task_running:
            messagebox.showerror(
                "Error!", "Please terminate the current training first or wait for the training to end."
            )
            return
        project_history_path = "./projects/{}/model".format(self.current_project)
        try:
            shutil.rmtree(project_history_path)
        except Exception as e:
            messagebox.showerror(
                "Error!", json.dumps(e.args)
            )
        messagebox.showinfo(
            "Error!", "Delete history successful!"
        )

    def clear_dataset(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please select a project first."
            )
            return
        if self.is_task_running:
            messagebox.showerror(
                "Error!", "Please terminate the current training first or wait for the training to end."
            )
            return
        project_history_path = "./projects/{}/dataset".format(self.current_project)
        try:
            shutil.rmtree(project_history_path)
            self.dataset_train_listbox.delete(1, tk.END)
            self.dataset_validation_listbox.delete(1, tk.END)
        except Exception as e:
            messagebox.showerror(
                "Error!", json.dumps(e.args)
            )
        messagebox.showinfo(
            "Error!", "Clear dataset successful!"
        )

    @staticmethod
    def popup_about():
        messagebox.showinfo("About", "Image Classification Wizard Tool based on Deep Learning 1.0\n\nAuthor's mailbox: kerlomz@gmail.com\n\nQQ Group: 857149419")

    def auto_loss(self, event):
        if self.comb_recurrent.get() == 'NoRecurrent':
            self.comb_loss.set("CrossEntropy")

    @staticmethod
    def get_param(src: dict, key, default=None):
        result = src.get(key)
        return result if result else default

    def read_conf(self, event):
        selected = self.comb_project_name.get()
        self.current_project = selected
        model_conf = ModelConfig(selected)
        self.edit_var.set(model_conf.memory_usage)
        self.size_val.set("[{}, {}]".format(model_conf.image_width, model_conf.image_height))
        self.resize_val.set(json.dumps(model_conf.resize))
        self.source_train_path_listbox.delete(0, tk.END)
        self.source_validation_path_listbox.delete(0, tk.END)
        self.dataset_validation_listbox.delete(0, tk.END)
        self.dataset_train_listbox.delete(0, tk.END)
        for source_train in self.get_param(model_conf.trains_path, DatasetType.Directory, default=[]):
            self.source_train_path_listbox.insert(tk.END, source_train)
        for source_validation in self.get_param(model_conf.validation_path, DatasetType.Directory, default=[]):
            self.source_validation_path_listbox.insert(tk.END, source_validation)
        self.label_num_spin.set(model_conf.max_label_num)
        self.comb_channel.set(model_conf.image_channel)
        self.comb_neu_cnn.set(model_conf.neu_cnn_param)
        self.comb_recurrent.set(model_conf.neu_recurrent_param)
        self.units_num_spin.set(model_conf.units_num)
        self.comb_loss.set(model_conf.loss_func_param)

        if isinstance(model_conf.category_param, list):
            self.category_entry['state'] = tk.NORMAL
            self.comb_category.set('CUSTOMIZED')
            self.category_val.set(json.dumps(model_conf.category_param, ensure_ascii=False))
        else:
            self.category_entry['state'] = tk.DISABLED
            self.comb_category.set(model_conf.category_param)

        self.comb_optimizer.set(model_conf.neu_optimizer_param)
        self.learning_rate_spin.set(model_conf.trains_learning_rate)
        self.end_acc_val.set(model_conf.trains_end_acc)
        self.end_cost_val.set(model_conf.trains_end_cost)
        self.end_epochs_spin.set(model_conf.trains_end_epochs)
        self.batch_size_val.set(model_conf.batch_size)
        self.validation_batch_size_val.set(model_conf.validation_batch_size)
        self.validation_num_val.set(model_conf.validation_set_num)

        self.data_augmentation_entity.binaryzation = model_conf.da_binaryzation
        self.data_augmentation_entity.median_blur = model_conf.da_median_blur
        self.data_augmentation_entity.gaussian_blur = model_conf.da_gaussian_blur
        self.data_augmentation_entity.equalize_hist = model_conf.da_equalize_hist
        self.data_augmentation_entity.laplace = model_conf.da_laplace
        self.data_augmentation_entity.warp_perspective = model_conf.da_warp_perspective
        self.data_augmentation_entity.rotate = model_conf.da_rotate
        self.data_augmentation_entity.sp_noise = model_conf.da_sp_noise
        self.data_augmentation_entity.brightness = model_conf.da_brightness
        self.data_augmentation_entity.hue = model_conf.da_hue
        self.data_augmentation_entity.channel_swap = model_conf.da_channel_swap
        self.data_augmentation_entity.random_blank = model_conf.da_random_blank
        self.data_augmentation_entity.random_transition = model_conf.da_random_transition

        self.pretreatment_entity.binaryzation = model_conf.pre_binaryzation
        self.pretreatment_entity.replace_transparent = model_conf.pre_replace_transparent
        self.pretreatment_entity.horizontal_stitching = model_conf.pre_horizontal_stitching
        self.pretreatment_entity.concat_frames = model_conf.pre_concat_frames
        self.pretreatment_entity.blend_frames = model_conf.pre_blend_frames

        for dataset_validation in self.get_param(model_conf.validation_path, DatasetType.TFRecords, default=[]):
            self.dataset_validation_listbox.insert(tk.END, dataset_validation)
        for dataset_train in self.get_param(model_conf.trains_path, DatasetType.TFRecords, default=[]):
            self.dataset_train_listbox.insert(tk.END, dataset_train)
        return model_conf

    @property
    def validation_batch_size(self):
        if self.dataset_validation_listbox.size() > 1:
            return self.validation_batch_size_val.get()
        else:
            return min(self.validation_batch_size_val.get(), self.validation_num_val.get())

    @property
    def device_usage(self):
        return self.edit_var.get()

    def save_conf(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        model_conf = ModelConfig(
            project_name=self.current_project,
            MemoryUsage=self.device_usage,
            CNNNetwork=self.neu_cnn,
            RecurrentNetwork=self.neu_recurrent,
            UnitsNum=self.units_num_spin.get(),
            Optimizer=self.optimizer,
            LossFunction=self.loss_func,
            Decoder=self.comb_loss.get(),
            ModelName=self.current_project,
            ModelField=ModelField.Image.value,
            ModelScene=ModelScene.Classification.value,
            Category=self.category,
            Resize=self.resize,
            ImageChannel=self.comb_channel.get(),
            ImageWidth=self.image_width,
            ImageHeight=self.image_height,
            MaxLabelNum=self.label_num_spin.get(),
            ReplaceTransparent=False,
            HorizontalStitching=False,
            OutputSplit='',
            LabelFrom=LabelFrom.FileName.value,
            ExtractRegex='.*?(?=_)',
            LabelSplit='',
            DatasetTrainsPath=self.dataset_value(
                dataset_type=DatasetType.TFRecords, mode=RunMode.Trains
            ),
            DatasetValidationPath=self.dataset_value(
                dataset_type=DatasetType.TFRecords, mode=RunMode.Validation
            ),
            SourceTrainPath=self.dataset_value(
                dataset_type=DatasetType.Directory, mode=RunMode.Trains
            ),
            SourceValidationPath=self.dataset_value(
                dataset_type=DatasetType.Directory, mode=RunMode.Validation
            ),
            ValidationSetNum=self.validation_num_val.get(),
            SavedSteps=100,
            ValidationSteps=500,
            EndAcc=self.end_acc_val.get(),
            EndCost=self.end_cost_val.get(),
            EndEpochs=self.end_epochs_spin.get(),
            BatchSize=self.batch_size_val.get(),
            ValidationBatchSize=self.validation_batch_size,
            LearningRate=self.learning_rate_spin.get(),
            DA_Binaryzation=self.data_augmentation_entity.binaryzation,
            DA_MedianBlur=self.data_augmentation_entity.median_blur,
            DA_GaussianBlur=self.data_augmentation_entity.gaussian_blur,
            DA_EqualizeHist=self.data_augmentation_entity.equalize_hist,
            DA_Laplace=self.data_augmentation_entity.laplace,
            DA_WarpPerspective=self.data_augmentation_entity.warp_perspective,
            DA_Rotate=self.data_augmentation_entity.rotate,
            DA_PepperNoise=self.data_augmentation_entity.sp_noise,
            DA_Brightness=self.data_augmentation_entity.brightness,
            DA_Saturation=self.data_augmentation_entity.saturation,
            DA_Hue=self.data_augmentation_entity.hue,
            DA_Gamma=self.data_augmentation_entity.gamma,
            DA_ChannelSwap=self.data_augmentation_entity.channel_swap,
            DA_RandomBlank=self.data_augmentation_entity.random_blank,
            DA_RandomTransition=self.data_augmentation_entity.random_transition,
            Pre_Binaryzation=self.pretreatment_entity.binaryzation,
            Pre_ReplaceTransparent=self.pretreatment_entity.replace_transparent,
            Pre_HorizontalStitching=self.pretreatment_entity.horizontal_stitching,
            Pre_ConcatFrames=self.pretreatment_entity.concat_frames,
            Pre_BlendFrames=self.pretreatment_entity.blend_frames,
        )
        model_conf.update()
        return model_conf

    def make_dataset(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        if self.is_task_running:
            messagebox.showerror(
                "Error!", "Please terminate the current training first or wait for the training to end."
            )
            return
        self.save_conf()
        self.button_state(self.btn_make_dataset, tk.DISABLED)
        model_conf = ModelConfig(self.current_project)
        train_path = self.dataset_value(DatasetType.Directory, RunMode.Trains)
        validation_path = self.dataset_value(DatasetType.Directory, RunMode.Validation)
        if len(train_path) < 1:
            messagebox.showerror(
                "Error!", "{} Sample set has not been added.".format(RunMode.Trains.value)
            )
            self.button_state(self.btn_make_dataset, tk.NORMAL)
            return
        self.threading_exec(
            lambda: DataSets(model_conf).make_dataset(
                trains_path=train_path,
                validation_path=validation_path,
                is_add=False,
                callback=lambda: self.button_state(self.btn_make_dataset, tk.NORMAL),
                msg=lambda x: tk.messagebox.showinfo('Make Dataset Status', x)
            )
        )

    @property
    def size(self):
        return self.json_filter(self.size_val.get(), int)

    @property
    def image_height(self):
        return self.size[1]

    @property
    def image_width(self):
        return self.size[0]

    @property
    def resize(self):
        return self.json_filter(self.resize_val.get(), int)

    @property
    def neu_cnn(self):
        return self.comb_neu_cnn.get()

    @property
    def neu_recurrent(self):
        return self.comb_recurrent.get()

    @property
    def loss_func(self):
        return self.comb_loss.get()

    @property
    def optimizer(self):
        return self.comb_optimizer.get()

    @staticmethod
    def json_filter(content, item_type):
        if not content:
            messagebox.showerror(
                "Error!", "To select a customized category, you must specify the category set manually."
            )
            return None
        try:
            content = json.loads(content)
        except ValueError as e:
            messagebox.showerror(
                "Error!", "Input must be of type JSON."
            )
            return None
        content = [item_type(i) for i in content]
        return content

    @property
    def category(self):
        comb_selected = self.comb_category.get()
        if not comb_selected:
            messagebox.showerror(
                "Error!", "Please select built-in category or custom category first"
            )
            return None
        if comb_selected == 'CUSTOMIZED':
            category_value = self.category_entry.get()
            category_value = category_value.replace("'", '"') if "'" in category_value else category_value
            category_value = self.json_filter(category_value, str)
        else:
            category_value = comb_selected
        return category_value

    def dataset_value(self, dataset_type: DatasetType, mode: RunMode):
        listbox = self.sample_map[dataset_type][mode]
        value = list(listbox.get(0, listbox.size() - 1))
        return value

    def compile_task(self):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        model_conf = ModelConfig(project_name=self.current_project)
        if not os.path.exists(model_conf.model_root_path):
            messagebox.showerror(
                "Error", "Model storage folder does not exist."
            )
            return
        if len(os.listdir(model_conf.model_root_path)) < 3:
            messagebox.showerror(
                "Error", "There is no training model record, please train before compiling."
            )
            return
        try:
            self.current_task = Trains(model_conf)
            self.current_task.compile_graph(0)
            status = 'Compile completed'
        except Exception as e:
            messagebox.showerror(
                e.__class__.__name__, json.dumps(e.args)
            )
            status = 'Compile failure'
        tk.messagebox.showinfo('Compile Status', status)

    def compile(self):
        self.job = self.threading_exec(
            lambda: self.compile_task()
        )

    def training_task(self):
        model_conf = ModelConfig(project_name=self.current_project)

        self.current_task = Trains(model_conf)
        try:
            self.button_state(self.btn_training, tk.DISABLED)
            self.button_state(self.btn_stop, tk.NORMAL)
            self.is_task_running = True
            self.current_task.train_process()
            status = 'Training completed'
        except Exception as e:
            traceback.print_exc()
            messagebox.showerror(
                e.__class__.__name__, json.dumps(e.args)
            )
            status = 'Training failure'
        self.button_state(self.btn_training, tk.NORMAL)
        self.button_state(self.btn_stop, tk.DISABLED)
        self.is_task_running = False
        tk.messagebox.showinfo('Training Status', status)

    @staticmethod
    def check_dataset(model_conf):
        trains_path = model_conf.trains_path[DatasetType.TFRecords]
        validation_path = model_conf.validation_path[DatasetType.TFRecords]
        if not trains_path or not validation_path:
            messagebox.showerror(
                "Error!", "Training set or validation set not defined."
            )
            return False
        for tp in trains_path:
            if not os.path.exists(tp):
                messagebox.showerror(
                    "Error!", "Training set path does not exist, please make dataset first"
                )
                return False
        for vp in validation_path:
            if not os.path.exists(vp):
                messagebox.showerror(
                    "Error!", "Validation set path does not exist, please make dataset first"
                )
                return False
        return True

    def start_training(self):
        if not self.check_resize():
            return
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please set the project name first."
            )
            return
        model_conf = self.save_conf()
        if not self.check_dataset(model_conf):
            return
        self.job = self.threading_exec(
            lambda: self.training_task()
        )

    def stop_training(self):
        self.current_task.stop_flag = True

    @property
    def project_names(self):
        return os.listdir(self.project_root_path)

    def fetch_projects(self):
        self.comb_project_name['values'] = self.project_names

    def browse_dataset(self, dataset_type: DatasetType, mode: RunMode):
        if not self.current_project:
            messagebox.showerror(
                "Error!", "Please define the project name first."
            )
            return
        filename = filedialog.askdirectory()
        if not filename:
            return
        is_sub = False
        for i, item in enumerate(os.scandir(filename)):
            if item.is_dir():
                path = item.path.replace("\\", "/")
                if self.sample_map[dataset_type][mode].size() == 0:
                    self.fetch_sample([path])
                self.sample_map[dataset_type][mode].insert(tk.END, path)
                if i > 0:
                    continue
                is_sub = True
            else:
                break
        if not is_sub:
            filename = filename.replace("\\", "/")
            if self.sample_map[dataset_type][mode].size() == 0:
                self.fetch_sample([filename])
            self.sample_map[dataset_type][mode].insert(tk.END, filename)

    @staticmethod
    def closest_category(category):
        category = set(category)
        category_group = dict()
        for key in SIMPLE_CATEGORY_MODEL.keys():
            category_set = set(category_extract(key))
            if category <= category_set:
                category_group[key] = len(category_set) - len(category)
        min_index = min(category_group.values())
        for k, v in category_group.items():
            if v == min_index:
                return k

    def fetch_sample(self, dataset_path):
        file_names = os.listdir(dataset_path[0])[0:100]
        category = list()
        len_label = -1

        for file_name in file_names:
            if "_" in file_name:
                label = file_name.split("_")[0]
                label = [i for i in label]
                len_label = len(label)
                category.extend(label)

        category_pram = self.closest_category(category)
        self.comb_category.set(category_pram)
        size = PilImage.open(os.path.join(dataset_path[0], file_names[0])).size
        self.size_val.set(json.dumps(size))
        self.resize_val.set(json.dumps(size))
        self.label_num_spin.set(len_label)

    def listbox_delete_item_callback(self, event, listbox: tk.Listbox):
        i = listbox.curselection()[0]
        listbox.delete(i)
        self.save_conf()

    def comb_category_callback(self, event):
        comb_selected = self.comb_category.get()
        if comb_selected == 'CUSTOMIZED':
            self.category_entry['state'] = tk.NORMAL
        else:
            self.category_entry.delete(0, tk.END)
            self.category_entry['state'] = tk.DISABLED

    def check_resize(self):
        param = OUTPUT_SHAPE1_MAP[NETWORK_MAP[self.neu_cnn]]
        shape1w = math.ceil(1.0*self.resize[0]/param[0])
        shape1h = math.ceil(1.0*self.resize[1]/param[0])
        input_s1 = shape1w * shape1h * param[1]
        label_num = int(self.label_num_spin.get())
        if input_s1 % label_num != 0:
            messagebox.showerror(
                "Error!", "Shape[1] = {} must divide the label_num = {}.".format(input_s1, label_num)
            )
            return False
        return True

    @staticmethod
    def resource_path(relative_path):
        try:
            # PyInstaller creates a temp folder and stores path in _MEIPASS
            base_path = sys._MEIPASS
        except AttributeError:
            base_path = os.path.abspath(".")
        return os.path.join(base_path, relative_path)


if __name__ == '__main__':
    root = tk.Tk()
    app = Wizard(root)
    root.mainloop()

