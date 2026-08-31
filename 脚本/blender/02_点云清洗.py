"""
Blender点云清洗脚本
作者：Claude AI
用途：清洗点云数据（去噪、降采样、修复）
执行者：Codex AI

使用方法：
blender --background --python 02_点云清洗.py -- <输入文件> <输出文件> [--downsample 0.5]
"""

import bpy
import sys
import json
import os
from pathlib import Path
import bmesh
import mathutils

class PointCloudCleaner:
    """点云清洗器"""

    def __init__(self, input_file, output_file, config=None):
        self.input_file = input_file
        self.output_file = output_file
        self.config = config or {}
        self.log = {
            "input_file": input_file,
            "output_file": output_file,
            "original_point_count": 0,
            "final_point_count": 0,
            "operations": [],
            "success": False
        }

    def clean(self):
        """执行清洗流程"""
        print(f"\n=== 开始清洗点云: {self.input_file} ===\n")

        # 1. 导入点云
        if not self._import_point_cloud():
            return False

        obj = bpy.context.active_object
        self.log["original_point_count"] = len(obj.data.vertices)
        print(f"原始点数: {self.log['original_point_count']:,}")

        # 2. 去除重复点
        self._remove_duplicates()

        # 3. 去除离群点（统计滤波）
        self._remove_outliers()

        # 4. 降采样
        if self.config.get("downsample", 0) > 0:
            self._downsample()

        # 5. 平滑（可选）
        if self.config.get("smooth", False):
            self._smooth()

        # 6. 导出清洗后的点云
        success = self._export_point_cloud()

        self.log["final_point_count"] = len(obj.data.vertices)
        self.log["success"] = success

        reduction = (1 - self.log["final_point_count"] / self.log["original_point_count"]) * 100
        print(f"\n最终点数: {self.log['final_point_count']:,} (减少 {reduction:.1f}%)")

        return success

    def _import_point_cloud(self):
        """导入点云"""
        try:
            # 清空场景
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

            ext = Path(self.input_file).suffix.lower()
            if ext == '.ply':
                bpy.ops.import_mesh.ply(filepath=self.input_file)
            elif ext == '.obj':
                bpy.ops.import_scene.obj(filepath=self.input_file)
            else:
                print(f"✗ 不支持的格式: {ext}")
                return False

            print("✓ 导入成功")
            return True

        except Exception as e:
            print(f"✗ 导入失败: {e}")
            return False

    def _remove_duplicates(self):
        """去除重复点"""
        print("\n[1/5] 去除重复点...")
        obj = bpy.context.active_object
        bpy.context.view_layer.objects.active = obj
        obj.select_set(True)

        before = len(obj.data.vertices)

        # 使用BMesh去重
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.remove_doubles(threshold=0.001)  # 0.001单位内的点视为重复
        bpy.ops.object.mode_set(mode='OBJECT')

        after = len(obj.data.vertices)
        removed = before - after

        self.log["operations"].append({
            "step": "remove_duplicates",
            "removed": removed,
            "remaining": after
        })

        print(f"✓ 去除 {removed:,} 个重复点")

    def _remove_outliers(self):
        """去除离群点（统计滤波）"""
        print("\n[2/5] 去除离群点...")
        obj = bpy.context.active_object
        mesh = obj.data

        before = len(mesh.vertices)

        # 简单的距离阈值过滤
        # 计算每个点到质心的距离，去除远离的点
        vertices = [v.co for v in mesh.vertices]

        if len(vertices) == 0:
            print("✓ 无点可处理")
            return

        # 计算质心
        center = mathutils.Vector((0, 0, 0))
        for v in vertices:
            center += v
        center /= len(vertices)

        # 计算距离
        distances = [(v - center).length for v in vertices]

        # 计算平均距离和标准差
        mean_dist = sum(distances) / len(distances)
        variance = sum((d - mean_dist) ** 2 for d in distances) / len(distances)
        std_dev = variance ** 0.5

        # 阈值：平均距离 + 3倍标准差
        threshold = mean_dist + 3 * std_dev

        # 标记要删除的顶点
        bpy.ops.object.mode_set(mode='EDIT')
        bm = bmesh.from_edit_mesh(mesh)

        verts_to_remove = [v for v, d in zip(bm.verts, distances) if d > threshold]
        bmesh.ops.delete(bm, geom=verts_to_remove, context='VERTS')

        bmesh.update_edit_mesh(mesh)
        bpy.ops.object.mode_set(mode='OBJECT')

        after = len(mesh.vertices)
        removed = before - after

        self.log["operations"].append({
            "step": "remove_outliers",
            "removed": removed,
            "remaining": after,
            "threshold": round(threshold, 3)
        })

        print(f"✓ 去除 {removed:,} 个离群点 (阈值: {threshold:.2f})")

    def _downsample(self):
        """降采样"""
        ratio = self.config.get("downsample", 0.5)
        print(f"\n[3/5] 降采样 (比例: {ratio})...")

        obj = bpy.context.active_object
        before = len(obj.data.vertices)

        # 使用Decimate修改器降采样
        mod = obj.modifiers.new(name="Decimate", type='DECIMATE')
        mod.decimate_type = 'COLLAPSE'
        mod.ratio = ratio

        bpy.ops.object.modifier_apply(modifier="Decimate")

        after = len(obj.data.vertices)
        removed = before - after

        self.log["operations"].append({
            "step": "downsample",
            "ratio": ratio,
            "removed": removed,
            "remaining": after
        })

        print(f"✓ 降采样完成，保留 {after:,} 个点")

    def _smooth(self):
        """平滑处理"""
        print("\n[4/5] 平滑处理...")
        obj = bpy.context.active_object

        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=2)
        bpy.ops.object.mode_set(mode='OBJECT')

        self.log["operations"].append({"step": "smooth"})
        print("✓ 平滑完成")

    def _export_point_cloud(self):
        """导出清洗后的点云"""
        print("\n[5/5] 导出点云...")

        try:
            # 确保输出目录存在
            output_path = Path(self.output_file)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # 导出
            ext = output_path.suffix.lower()
            if ext == '.ply':
                bpy.ops.export_mesh.ply(
                    filepath=self.output_file,
                    use_selection=True,
                    use_normals=True,
                    use_colors=True
                )
            elif ext == '.obj':
                bpy.ops.export_scene.obj(
                    filepath=self.output_file,
                    use_selection=True
                )
            else:
                print(f"✗ 不支持的输出格式: {ext}")
                return False

            print(f"✓ 导出成功: {self.output_file}")
            return True

        except Exception as e:
            print(f"✗ 导出失败: {e}")
            return False

    def save_log(self, output_dir):
        """保存处理日志"""
        log_path = Path(output_dir) / f"{Path(self.input_file).stem}_清洗日志.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)

        with open(log_path, 'w', encoding='utf-8') as f:
            json.dump(self.log, f, ensure_ascii=False, indent=2)

        print(f"\n日志已保存: {log_path}")


def main():
    """主函数 - Codex执行入口"""
    print("\n" + "="*60)
    print("点云清洗脚本 - Claude AI 编写")
    print("执行者: Codex AI")
    print("="*60 + "\n")

    # 解析命令行参数
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []

    if len(argv) < 2:
        print("错误：参数不足")
        print("用法: blender --background --python 02_点云清洗.py -- <输入> <输出> [--downsample 0.5]")
        sys.exit(1)

    input_file = argv[0]
    output_file = argv[1]

    # 解析可选参数
    config = {}
    for i in range(2, len(argv)):
        if argv[i] == '--downsample' and i + 1 < len(argv):
            config['downsample'] = float(argv[i + 1])
        elif argv[i] == '--smooth':
            config['smooth'] = True

    # 执行清洗
    cleaner = PointCloudCleaner(input_file, output_file, config)
    success = cleaner.clean()

    if success:
        # 保存日志
        log_dir = Path(__file__).parent.parent.parent / "输出" / "日志"
        cleaner.save_log(log_dir)
        print("\n✓ 清洗任务完成")
    else:
        print("\n✗ 清洗失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
