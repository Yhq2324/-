"""
Blender点云分析脚本
作者：Claude AI
用途：分析点云文件的质量、密度、范围等信息
执行者：Codex AI

使用方法：
blender --background --python 01_点云分析.py -- <点云文件路径>
"""

import bpy
import sys
import json
import os
from pathlib import Path
import math

class PointCloudAnalyzer:
    """点云分析器"""

    def __init__(self, input_file):
        self.input_file = input_file
        self.report = {
            "file_name": os.path.basename(input_file),
            "file_path": input_file,
            "file_size_mb": 0,
            "point_count": 0,
            "has_colors": False,
            "has_normals": False,
            "bounding_box": {},
            "dimensions": {},
            "density": 0,
            "quality_score": 0,
            "recommendations": []
        }

    def analyze(self):
        """执行完整分析"""
        print(f"\n=== 开始分析点云: {self.input_file} ===\n")

        # 1. 获取文件信息
        self._analyze_file_info()

        # 2. 导入点云
        success = self._import_point_cloud()
        if not success:
            return None

        # 3. 分析几何信息
        self._analyze_geometry()

        # 4. 分析数据完整性
        self._analyze_data_completeness()

        # 5. 计算质量分数
        self._calculate_quality_score()

        # 6. 生成建议
        self._generate_recommendations()

        # 7. 清理场景
        self._cleanup()

        print(f"\n=== 分析完成 ===\n")
        return self.report

    def _analyze_file_info(self):
        """分析文件基本信息"""
        file_size = os.path.getsize(self.input_file)
        self.report["file_size_mb"] = round(file_size / (1024 * 1024), 2)
        print(f"文件大小: {self.report['file_size_mb']} MB")

    def _import_point_cloud(self):
        """导入点云文件"""
        try:
            # 清空场景
            bpy.ops.object.select_all(action='SELECT')
            bpy.ops.object.delete()

            # 根据文件扩展名选择导入方式
            ext = Path(self.input_file).suffix.lower()

            if ext == '.ply':
                bpy.ops.import_mesh.ply(filepath=self.input_file)
            elif ext == '.obj':
                bpy.ops.import_scene.obj(filepath=self.input_file)
            elif ext == '.stl':
                bpy.ops.import_mesh.stl(filepath=self.input_file)
            else:
                print(f"警告：不支持的文件格式 {ext}")
                self.report["recommendations"].append(f"请转换为.ply格式")
                return False

            print("✓ 点云导入成功")
            return True

        except Exception as e:
            print(f"✗ 导入失败: {e}")
            self.report["recommendations"].append(f"文件可能损坏或格式不正确")
            return False

    def _analyze_geometry(self):
        """分析几何信息"""
        obj = bpy.context.active_object
        if not obj:
            return

        # 获取网格数据
        mesh = obj.data

        # 点数（顶点数）
        self.report["point_count"] = len(mesh.vertices)
        print(f"点数: {self.report['point_count']:,}")

        # 包围盒
        bbox = [obj.matrix_world @ v.co for v in mesh.vertices]
        min_x = min(v.x for v in bbox)
        max_x = max(v.x for v in bbox)
        min_y = min(v.y for v in bbox)
        max_y = max(v.y for v in bbox)
        min_z = min(v.z for v in bbox)
        max_z = max(v.z for v in bbox)

        self.report["bounding_box"] = {
            "min": [round(min_x, 3), round(min_y, 3), round(min_z, 3)],
            "max": [round(max_x, 3), round(max_y, 3), round(max_z, 3)]
        }

        # 尺寸
        dim_x = max_x - min_x
        dim_y = max_y - min_y
        dim_z = max_z - min_z
        self.report["dimensions"] = {
            "x": round(dim_x, 3),
            "y": round(dim_y, 3),
            "z": round(dim_z, 3),
            "diagonal": round(math.sqrt(dim_x**2 + dim_y**2 + dim_z**2), 3)
        }

        print(f"尺寸: {dim_x:.2f} x {dim_y:.2f} x {dim_z:.2f}")

        # 密度估算（点数/体积）
        volume = dim_x * dim_y * dim_z
        if volume > 0:
            self.report["density"] = round(self.report["point_count"] / volume, 2)
            print(f"点密度: {self.report['density']:.2f} 点/立方单位")

    def _analyze_data_completeness(self):
        """分析数据完整性"""
        obj = bpy.context.active_object
        if not obj:
            return

        mesh = obj.data

        # 检查顶点颜色
        if mesh.vertex_colors:
            self.report["has_colors"] = True
            print("✓ 包含颜色信息")
        else:
            print("✗ 不含颜色信息")

        # 检查法线（对于点云，通常需要计算）
        if len(mesh.vertices) > 0:
            # 简单检查：如果所有法线都是(0,0,0)则认为没有法线
            has_valid_normals = any(
                v.normal.length > 0.01 for v in mesh.vertices[:100]  # 抽样检查
            )
            self.report["has_normals"] = has_valid_normals
            if has_valid_normals:
                print("✓ 包含法线信息")
            else:
                print("✗ 不含法线信息（需要重建）")

    def _calculate_quality_score(self):
        """计算质量分数 (0-100)"""
        score = 0

        # 点数评分 (0-40分)
        point_count = self.report["point_count"]
        if point_count > 10_000_000:
            score += 40
        elif point_count > 1_000_000:
            score += 30
        elif point_count > 100_000:
            score += 20
        elif point_count > 10_000:
            score += 10
        else:
            score += 5

        # 颜色信息 (0-20分)
        if self.report["has_colors"]:
            score += 20

        # 法线信息 (0-20分)
        if self.report["has_normals"]:
            score += 20

        # 密度评分 (0-20分)
        density = self.report["density"]
        if density > 1000:
            score += 20
        elif density > 100:
            score += 15
        elif density > 10:
            score += 10
        else:
            score += 5

        self.report["quality_score"] = score
        print(f"\n质量评分: {score}/100")

    def _generate_recommendations(self):
        """生成处理建议"""
        recommendations = self.report["recommendations"]

        # 基于点数的建议
        point_count = self.report["point_count"]
        if point_count > 50_000_000:
            recommendations.append("点数极多，建议分批处理或大幅降采样")
        elif point_count > 10_000_000:
            recommendations.append("点数较多，建议降采样到50%")
        elif point_count < 10_000:
            recommendations.append("点数较少，可能需要更密集的扫描")

        # 基于数据完整性的建议
        if not self.report["has_colors"]:
            recommendations.append("缺少颜色信息，材质需要手动创建")

        if not self.report["has_normals"]:
            recommendations.append("缺少法线信息，需要在网格转换时计算")

        # 基于密度的建议
        density = self.report["density"]
        if density < 1:
            recommendations.append("点密度低，可能导致网格质量差")
        elif density > 10000:
            recommendations.append("点密度极高，可以降采样以提高处理速度")

        # 基于文件大小的建议
        file_size = self.report["file_size_mb"]
        if file_size > 1000:
            recommendations.append("文件很大，建议分割处理")

        print("\n建议:")
        for i, rec in enumerate(recommendations, 1):
            print(f"  {i}. {rec}")

    def _cleanup(self):
        """清理场景"""
        bpy.ops.object.select_all(action='SELECT')
        bpy.ops.object.delete()

    def save_report(self, output_dir):
        """保存分析报告"""
        output_path = Path(output_dir) / f"{Path(self.input_file).stem}_分析报告.json"
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.report, f, ensure_ascii=False, indent=2)

        print(f"\n报告已保存到: {output_path}")
        return str(output_path)


def main():
    """主函数 - Codex执行入口"""
    print("\n" + "="*60)
    print("点云分析脚本 - Claude AI 编写")
    print("执行者: Codex AI")
    print("="*60 + "\n")

    # 获取命令行参数
    argv = sys.argv
    argv = argv[argv.index("--") + 1:] if "--" in argv else []

    if len(argv) < 1:
        print("错误：请提供点云文件路径")
        print("用法: blender --background --python 01_点云分析.py -- <点云文件>")
        sys.exit(1)

    input_file = argv[0]

    if not os.path.exists(input_file):
        print(f"错误：文件不存在: {input_file}")
        sys.exit(1)

    # 执行分析
    analyzer = PointCloudAnalyzer(input_file)
    report = analyzer.analyze()

    if report:
        # 保存报告
        output_dir = Path(__file__).parent.parent.parent / "输出" / "报告"
        analyzer.save_report(output_dir)

        print("\n✓ 分析任务完成")
        print(f"✓ 质量评分: {report['quality_score']}/100")
        print(f"✓ 点数: {report['point_count']:,}")
    else:
        print("\n✗ 分析失败")
        sys.exit(1)


if __name__ == "__main__":
    main()
